#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ACL Paper Track Classification using TF-IDF
=====================================================

This script uses TF-IDF vectorization and a Logistic Regression classifier to categorize
ACL research papers into their respective tracks based on their titles and abstracts.
It evaluates the performance on the ACL25_ThemeData dataset.

Author: Eric Chen & GitHub Copilot
Date: June 9, 2025
"""

# I. Imports - All necessary libraries
import os
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from sklearn.metrics import (
    accuracy_score, 
    precision_recall_fscore_support, 
    confusion_matrix
)
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import LabelEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

def load_data(csv_path):
    """
    Load data from CSV file
    
    Args:
        csv_path (str): Path to the CSV file
        
    Returns:
        tuple: DataFrame, label encoder, unique labels
    """
    print(f"Loading data from {csv_path}...")
    # Load data
    df = pd.read_csv(csv_path)
    
    # Check for required columns
    required_columns = ['Title', 'Track Theme']
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Required column '{col}' not found in the dataset")
    
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
    
    # Encode labels
    le = LabelEncoder()
    df['label_id'] = le.fit_transform(df['Track Theme'])
    unique_labels = le.classes_
    
    print(f"Found {len(unique_labels)} unique tracks.")
    
    return df, le, unique_labels

def compute_metrics(y_true, y_pred):
    """
    Compute evaluation metrics for the model
    
    Args:
        y_true: True labels
        y_pred: Predicted labels
        
    Returns:
        dict: Dictionary of metrics including micro/macro F1 scores
    """
    # Calculate metrics
    accuracy = accuracy_score(y_true, y_pred)
    
    # Calculate macro metrics
    precision_macro, recall_macro, f1_macro, _ = precision_recall_fscore_support(
        y_true, y_pred, average='macro', zero_division=0
    )
    
    # Calculate micro metrics
    precision_micro, recall_micro, f1_micro, _ = precision_recall_fscore_support(
        y_true, y_pred, average='micro', zero_division=0
    )
    
    # Calculate weighted metrics
    precision_weighted, recall_weighted, f1_weighted, _ = precision_recall_fscore_support(
        y_true, y_pred, average='weighted', zero_division=0
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

def plot_confusion_matrix(y_true, y_pred, labels, model_name):
    """
    Computes, plots, and saves the confusion matrix
    
    Args:
        y_true: True labels
        y_pred: Predicted labels
        labels: List of label names
        model_name: Name of the model (for saving the figure)
    """
    print(f"\nGenerating confusion matrix for {model_name}...")
    
    # Compute the confusion matrix
    cm = confusion_matrix(y_true, y_pred)

    # Plot the confusion matrix using seaborn
    plt.figure(figsize=(18, 15))  # Adjust size for better readability
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                xticklabels=labels, yticklabels=labels)
    
    plt.title(f'Confusion Matrix - {model_name}', fontsize=20)
    plt.ylabel('True Label', fontsize=16)
    plt.xlabel('Predicted Label', fontsize=16)
    plt.xticks(rotation=45, ha="right", fontsize=12)
    plt.yticks(rotation=0, fontsize=12)
    plt.tight_layout()  # Adjust layout to make sure labels fit

    # Save the figure to a file
    output_path = f"./visualizations/confusion_matrix_{model_name.lower().replace(' ', '_')}.png"
    plt.savefig(output_path)
    print(f"Confusion matrix plot saved to {output_path}")
    
    # Close the figure to free memory
    plt.close()



def classify_with_tfidf(df, label_encoder):
    """
    Classify papers using TF-IDF and a Logistic Regression classifier
    
    Args:
        df (pd.DataFrame): DataFrame with the data
        label_encoder (LabelEncoder): Fitted label encoder
        
    Returns:
        dict: Dictionary of metrics
    """
    print("\n===== Evaluating TF-IDF Classifier =====")
    
    # Split data
    train_df, test_df = train_test_split(
        df, test_size=0.2, random_state=42, stratify=df['label_id']
    )
    
    # Extract TF-IDF features
    print("Extracting TF-IDF features...")
    tfidf = TfidfVectorizer(
        max_features=10000,
        stop_words='english',
        ngram_range=(1, 2)  # Include bigrams
    )
    
    train_features = tfidf.fit_transform(train_df['text_input'])
    test_features = tfidf.transform(test_df['text_input'])
    
    print(f"TF-IDF features shape: {train_features.shape}")
    
    # Train a logistic regression classifier
    print("Training a logistic regression classifier on TF-IDF features...")
    classifier = LogisticRegression(
        max_iter=1000, 
        class_weight='balanced', 
        n_jobs=-1,
        C=1.0,
        solver='liblinear'
    )
    classifier.fit(train_features, train_df['label_id'])
    
    # Predict
    print("Making predictions...")
    test_pred = classifier.predict(test_features)
    
    # Compute metrics
    metrics = compute_metrics(test_df['label_id'], test_pred)
    
    # Plot confusion matrix
    plot_confusion_matrix(
        test_df['label_id'], 
        test_pred,
        label_encoder.classes_,
        "TF-IDF Classifier"
    )
    
    # Save the model
    model_dir = "classifier_models/tfidf"
    os.makedirs(model_dir, exist_ok=True)
    
    # Import needed for saving the model
    import joblib
    joblib.dump(classifier, f"{model_dir}/tfidf_classifier.joblib")
    joblib.dump(tfidf, f"{model_dir}/tfidf_vectorizer.joblib")
    joblib.dump(label_encoder, f"{model_dir}/label_encoder.joblib")
    print(f"Model and vectorizer saved to {model_dir}/")
    
    return metrics, test_df['label_id'], test_pred

def print_metrics(metrics, model_name):
    """
    Print metrics in a formatted way
    
    Args:
        metrics (dict): Dictionary of metrics
        model_name (str): Name of the model
    """
    print(f"\n===== {model_name} Performance Metrics =====")
    print(f"Accuracy: {metrics['accuracy']:.4f}")
    print(f"Micro-F1 Score: {metrics['f1_micro']:.4f}")
    print(f"Macro-F1 Score: {metrics['f1_macro']:.4f}")
    print(f"Weighted-F1 Score: {metrics['f1_weighted']:.4f}")
    print("==================================\n")
    
    # Print more detailed metrics
    print(f"Detailed {model_name} metrics:")
    print(f"  Precision (macro): {metrics['precision_macro']:.4f}")
    print(f"  Recall (macro): {metrics['recall_macro']:.4f}")
    print(f"  Precision (weighted): {metrics['precision_weighted']:.4f}")
    print(f"  Recall (weighted): {metrics['recall_weighted']:.4f}")
    print("==================================\n")

def main():
    """
    Main function to run the TF-IDF classification
    """
    # Path to data
    data_path = ".\\data\\ACL25_ThemeData.csv"
    
    # Load data
    df, label_encoder, unique_labels = load_data(data_path)
    
    # Get metrics for TF-IDF classifier
    tfidf_metrics, _, _ = classify_with_tfidf(df, label_encoder)
    print_metrics(tfidf_metrics, "TF-IDF Classifier")
    
    # Save detailed metrics to CSV
    # metrics_df = pd.DataFrame([tfidf_metrics])
    # metrics_df.to_csv('tfidf_classifier_metrics.csv', index=False)
    # print("Detailed metrics saved to 'tfidf_classifier_metrics.csv'")

if __name__ == "__main__":
    main()
