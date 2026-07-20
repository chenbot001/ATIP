#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ACL Paper Track Classification using SciBERT Fine-tuning
========================================================

This script fine-tunes a pre-trained SciBERT model to classify ACL research papers
into their respective tracks based on their titles and abstracts.

Author: Eric Chen & GitHub Copilot
Date: June 7, 2025
"""

# I. Imports - All necessary libraries
import os
import json
import numpy as np
import pandas as pd
import torch
import seaborn as sns
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification, 
    Trainer, 
    TrainingArguments,
    EarlyStoppingCallback
)
from datasets import Dataset
from sklearn.utils.class_weight import compute_class_weight

class WeightedLossTrainer(Trainer):
    """
    A custom Trainer that applies class weights to the loss function.
    """
    def __init__(self, *args, class_weights=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Move weights to the correct device
        if class_weights is not None:
            self.class_weights = class_weights.to(self.args.device)
        else:
            self.class_weights = None

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        """
        Overrides the default loss computation to use weighted cross-entropy.
        """
        # Extract labels
        labels = inputs.pop("labels")
        
        # Forward pass
        outputs = model(**inputs)
        logits = outputs.get("logits")
        
        # Manually compute loss with class weights
        loss_fct = torch.nn.CrossEntropyLoss(weight=self.class_weights)
        loss = loss_fct(logits.view(-1, logits.shape[-1]), labels.view(-1))
        
        return (loss, outputs) if return_outputs else loss

# Check for GPU availability
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")

# II. Data Handling and Preprocessing
def load_and_preprocess_data(csv_path):
    """
    Load and preprocess data from CSV file.
    
    Args:
        csv_path (str): Path to the CSV file
        
    Returns:
        tuple: train_dataset, val_dataset, label2id, id2label
    """
    print(f"Loading data from {csv_path}...")
    # Load data
    df = pd.read_csv(csv_path)
    
    # Check if abstract column is available
    has_abstract = 'Abstract' in df.columns
    
    # Create text_input column
    if has_abstract:
        # Combine title and abstract, handle missing abstracts
        df['text_input'] = df.apply(
            lambda x: x['Title'] + ' [SEP] ' + str(x['Abstract']) 
            if pd.notna(x['Abstract']) else x['Title'],
            axis=1
        )
    else:
        df['text_input'] = df['Title']
    
    # Create label encoding
    unique_tracks = df['Track Theme'].unique()
    label2id = {track: idx for idx, track in enumerate(unique_tracks)}
    id2label = {idx: track for track, idx in label2id.items()}
    
    # Add label column
    df['label'] = df['Track Theme'].map(label2id)
    
    print(f"Found {len(unique_tracks)} unique tracks.")
    
    # Split data into train and validation sets
    train_df, val_df = train_test_split(
        df, 
        test_size=0.2, 
        random_state=42, 
        stratify=df['label']
    )
    
    print(f"Train set: {len(train_df)} samples, Validation set: {len(val_df)} samples")
    
    # Convert to Hugging Face datasets
    train_dataset = Dataset.from_pandas(train_df[['text_input', 'label']])
    val_dataset = Dataset.from_pandas(val_df[['text_input', 'label']])
    
    return train_dataset, val_dataset, label2id, id2label

# III. Tokenization
def tokenize_data(dataset, tokenizer):
    """
    Tokenize the dataset using the provided tokenizer
    
    Args:
        dataset (Dataset): Hugging Face Dataset
        tokenizer (AutoTokenizer): Pretrained tokenizer
        
    Returns:
        Dataset: Tokenized dataset
    """
    def tokenize_function(examples):
        return tokenizer(
            examples['text_input'],
            truncation=True,
            padding="max_length",
            max_length=512
        )
    
    tokenized_dataset = dataset.map(
        tokenize_function,
        batched=True,
        desc="Tokenizing dataset"
    )
    
    # Set format for pytorch
    tokenized_dataset = tokenized_dataset.remove_columns(['text_input'])
    tokenized_dataset = tokenized_dataset.rename_column('label', 'labels')
    tokenized_dataset.set_format('torch')
    
    return tokenized_dataset

# VI. Evaluation Metrics
def compute_metrics(eval_pred):
    """
    Compute evaluation metrics for the model
    
    Args:
        eval_pred (EvalPrediction): Contains predictions and labels
        
    Returns:
        dict: Dictionary of metrics including micro/macro F1 scores
    """
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    
    # Calculate metrics
    accuracy = accuracy_score(labels, preds)
    
    # Calculate macro metrics
    precision_macro, recall_macro, f1_macro, _ = precision_recall_fscore_support(
        labels, preds, average='macro', zero_division=0
    )
    
    # Calculate micro metrics
    precision_micro, recall_micro, f1_micro, _ = precision_recall_fscore_support(
        labels, preds, average='micro', zero_division=0
    )
    
    # Calculate weighted metrics
    precision_weighted, recall_weighted, f1_weighted, _ = precision_recall_fscore_support(
        labels, preds, average='weighted', zero_division=0
    )
    
    # Return metrics dictionary
    return {
        'accuracy': accuracy,
        'precision_macro': precision_macro,
        'recall_macro': recall_macro,
        'f1_macro': f1_macro,
        'precision_micro': precision_micro,
        'recall_micro': recall_micro,
        'f1_micro': f1_micro,
        'precision_weighted': precision_weighted,
        'recall_weighted': recall_weighted,
        'f1_weighted': f1_weighted
    }

# VII. Training Execution
def train_model(train_dataset, val_dataset, num_labels, label2id, id2label):
    """
    Train the model with the specified datasets and configuration
    
    Args:
        train_dataset (Dataset): Training dataset
        val_dataset (Dataset): Validation dataset
        num_labels (int): Number of unique labels/tracks
        label2id (dict): Mapping from label names to IDs
        id2label (dict): Mapping from IDs to label names
        
    Returns:
        tuple: Trained model, tokenizer
    """
    print("Initializing model and tokenizer...")
    # Load tokenizer and model
    tokenizer = AutoTokenizer.from_pretrained("allenai/scibert_scivocab_uncased")
    model = AutoModelForSequenceClassification.from_pretrained(
        "allenai/scibert_scivocab_uncased",
        num_labels=num_labels,
        label2id=label2id,
        id2label=id2label
    ).to(device)
    
    # Tokenize datasets
    print("Tokenizing datasets...")
    tokenized_train_dataset = tokenize_data(train_dataset, tokenizer)
    tokenized_val_dataset = tokenize_data(val_dataset, tokenizer)
      
    # Calculate class weights for the weighted loss function
    print("Calculating class weights to handle data imbalance...")
    train_labels = np.array(train_dataset['label'])
    class_weights = compute_class_weight(
        class_weight='balanced',
        classes=np.unique(train_labels),
        y=train_labels
    )
    weights_tensor = torch.tensor(class_weights, dtype=torch.float)
    print("Class weights calculated.")
      # Define training arguments
    print("Setting up training arguments...")
    training_args = TrainingArguments(
        output_dir="classifier_models\scibert_ft",
        num_train_epochs=5,
        per_device_train_batch_size=4,
        per_device_eval_batch_size=8,
        gradient_accumulation_steps=8,  # Effective batch size: 32
        learning_rate=3e-5,
        weight_decay=0.01,
        eval_strategy="steps",  # Corrected from eval_strategy
        eval_steps=200,  # Adjust based on dataset size
        save_strategy="steps",
        save_steps=200,
        logging_dir="./logs",
        logging_steps=50,
        fp16=True,
        load_best_model_at_end=True,
        metric_for_best_model="eval_f1_macro",
        greater_is_better=True,
        report_to="tensorboard"
    )
    
    # Initialize the new WeightedLossTrainer
    print("Initializing WeightedLossTrainer...")
    trainer = WeightedLossTrainer( # Use the new custom class
        model=model,
        args=training_args,
        train_dataset=tokenized_train_dataset,
        eval_dataset=tokenized_val_dataset,
        tokenizer=tokenizer,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=3)],
        class_weights=weights_tensor # Pass the calculated weights
    )
    
    # Train model
    print("Starting training...")
    trainer.train()
    
    # Save best model
    print("Saving the best model...")
    final_model_path = "./final_track_classifier_model"
    trainer.save_model(final_model_path)
    tokenizer.save_pretrained(final_model_path)
    
    # Save label2id mapping
    label2id_path = os.path.join(final_model_path, "label2id.json")
    with open(label2id_path, 'w') as f:
        json.dump(label2id, f)
    
    print(f"Model and tokenizer saved to {final_model_path}")
    
    return model, tokenizer

# VIII. Inference Function
def predict_track(texts, model_path, tokenizer_path, label2id_path):
    """
    Predict track for given paper titles/texts
    
    Args:
        texts (list): List of strings (paper titles or title+abstract)
        model_path (str): Path to saved model
        tokenizer_path (str): Path to saved tokenizer
        label2id_path (str): Path to label2id mapping
        
    Returns:
        list: Predicted track names
    """
    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_path)
    
    # Determine device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # Load model
    model = AutoModelForSequenceClassification.from_pretrained(model_path).to(device)
    
    # Load label2id mapping
    with open(label2id_path, 'r') as f:
        label2id = json.load(f)
    
    # Create id2label from label2id
    id2label = {int(idx): track for track, idx in label2id.items()}
    
    # Set model to evaluation mode
    model.eval()
    
    # Tokenize inputs
    inputs = tokenizer(
        texts, 
        padding=True, 
        truncation=True, 
        max_length=512, 
        return_tensors="pt"
    ).to(device)
    
    # Perform inference
    with torch.no_grad():
        outputs = model(**inputs)
    
    # Get predicted class IDs
    predicted_ids = torch.argmax(outputs.logits, dim=-1).cpu().tolist()
    
    # Convert IDs to track names
    predicted_tracks = [id2label[idx] for idx in predicted_ids]
    
    return predicted_tracks

# Evaluate model
def evaluate_model(model, tokenizer, val_dataset):
    """
    Evaluate model performance on validation dataset
    
    Args:
        model: Fine-tuned model
        tokenizer: Tokenizer
        val_dataset: Validation dataset
        
    Returns:
        dict: Evaluation metrics
    """
    # Tokenize validation dataset if needed
    if 'input_ids' not in val_dataset.features:
        val_dataset = tokenize_data(val_dataset, tokenizer)
    
    # Initialize trainer for evaluation
    eval_trainer = Trainer(
        model=model,
        compute_metrics=compute_metrics,
    )
    
    # Evaluate and return metrics
    metrics = eval_trainer.evaluate(val_dataset)
    
    return metrics

def plot_confusion_matrix(model, tokenizer, eval_dataset, id2label):
    """
    Computes, plots, and saves the confusion matrix for the evaluation dataset.
    
    Args:
        model: The fine-tuned model.
        tokenizer: The tokenizer.
        eval_dataset (Dataset): The validation dataset (untokenized).
        id2label (dict): Mapping from label IDs to track names.
    """
    print("\nGenerating confusion matrix...")
    
    # Tokenize the dataset if it's not already tokenized
    if 'input_ids' not in eval_dataset.features:
        tokenized_eval_dataset = tokenize_data(eval_dataset, tokenizer)
    else:
        tokenized_eval_dataset = eval_dataset

    # Create a Trainer instance just for running predictions
    eval_trainer = Trainer(model=model)
    
    # Get predictions
    predictions = eval_trainer.predict(tokenized_eval_dataset)
    
    # The predictions object contains logits, use argmax to get predicted labels
    pred_labels = np.argmax(predictions.predictions, axis=-1)
    
    # The true labels are also in the predictions object
    true_labels = predictions.label_ids

    # Ensure true_labels and pred_labels are numpy arrays and not None
    if true_labels is None or pred_labels is None:
        raise ValueError("True labels or predicted labels are None. Cannot compute confusion matrix.")
    true_labels = np.array(true_labels)
    pred_labels = np.array(pred_labels)

    # Compute the confusion matrix
    cm = confusion_matrix(true_labels, pred_labels)

    # Get track names for labels
    track_names = [id2label[i] for i in range(len(id2label))]

    # Plot the confusion matrix using seaborn
    plt.figure(figsize=(18, 15))  # Adjust size for better readability
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                xticklabels=track_names, yticklabels=track_names)
    
    plt.title('Confusion Matrix', fontsize=20)
    plt.ylabel('True Label', fontsize=16)
    plt.xlabel('Predicted Label', fontsize=16)
    plt.xticks(rotation=45, ha="right", fontsize=12)
    plt.yticks(rotation=0, fontsize=12)
    plt.tight_layout()  # Adjust layout to make sure labels fit

    # Save the figure to a file
    output_path = "./visualizations/confusion_matrix_scibert_ft.png"
    plt.savefig(output_path)
    print(f"Confusion matrix plot saved to {output_path}")
    
    # Optionally display the plot
    plt.show()

# Main execution block
if __name__ == "__main__":
    # Path to data
    data_path = "./data/ACL25_ThemeData.csv"
    
    # Load and preprocess data
    train_dataset, val_dataset, label2id, id2label = load_and_preprocess_data(data_path)
    
    # Train model
    model, tokenizer = train_model(
        train_dataset, 
        val_dataset, 
        num_labels=len(label2id), 
        label2id=label2id, 
        id2label=id2label
    )
      # Evaluate model
    print("\nEvaluating model on validation set...")
    metrics = evaluate_model(model, tokenizer, val_dataset)

    # Print full metrics for detailed analysis
    print("Full validation metrics:")
    for key, value in metrics.items():
        if isinstance(value, (float, int)):
            print(f"  {key}: {value:.4f}")
        else:
            print(f"  {key}: {value}")
    
    plot_confusion_matrix(model, tokenizer, val_dataset, id2label)

    # # Example usage of predict_track function
    # print("\nExample inference:")
    # sample_texts = [
    #     "Transformer-based Models for Multilingual NLP Tasks",
    #     "A Survey on Bias in Large Language Models",
    #     "Resource-Efficient Fine-tuning of Language Models for Low-Resource Languages"
    # ]
    
    # predictions = predict_track(
    #     sample_texts,
    #     "./final_best_model",
    #     "./final_best_model", 
    #     "./final_best_model/label2id.json"
    # )
    
    # print("\nSample predictions:")
    # for text, pred in zip(sample_texts, predictions):
    #     print(f"Text: {text}\nPredicted Track: {pred}\n")
    
    print("Fine-tuning and evaluation complete!")
