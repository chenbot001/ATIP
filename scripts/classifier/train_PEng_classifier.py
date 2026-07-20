import os
import pandas as pd
from sklearn.metrics import classification_report
from tqdm import tqdm
import sys
import dashscope
from dashscope import Generation
from http import HTTPStatus 
from sklearn.metrics import accuracy_score, f1_score
from sklearn.metrics import ConfusionMatrixDisplay
import matplotlib.pyplot as plt

# Configuration
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
if not dashscope.api_key:
    print("Error: DASHSCOPE_API_KEY environment variable is not set.")
    sys.exit(1)

INPUT_CSV_PATH = "C:/Eric/Projects/AI_Researcher_Network/data/ACL25_ThemeData.csv"

# Data Loading and Preparation
def load_data(input_csv_path):
    df = pd.read_csv(input_csv_path)
    unique_tracks = df['Track Theme'].unique().tolist()
    few_shot_examples = [
        {'Title': 'Small Changes, Big Impact: How Manipulating a Few Neurons Can Drastically Alter LLM Aggression', 'Track': 'Language Modeling'},
        {'Title': 'Error-driven Data-efficient Large Multimodal Model Tuning', 'Track': 'Efficient/Low-Resource Methods for NLP'},
        {'Title': 'CoinMath: Harnessing the Power of Coding Instruction for Math LLM', 'Track': 'NLP Applications'},
        {'Title': 'Rethinking Repetition Problems of LLMs in Code Generation', 'Track': 'Generation'},
        {'Title': 'Evaluating Lexical Proficiency in Neural Language Models', 'Track': 'Resources and Evaluation'},
    ]
    test_set = df[~df['Title'].isin([ex['Title'] for ex in few_shot_examples])]
    return test_set, unique_tracks, few_shot_examples

# Few-Shot Prompt Engineering
def generate_prompt(title, examples, tracks):
    PROMPT_TEMPLATE = """You are an expert academic research classifier. Your task is to classify the given research paper title into one of the following predefined tracks.

### Available Tracks
{tracks}

### Examples
{examples}

### Task
Now, classify the following title into one of the tracks listed above. Respond with only the track name and nothing else.

Title: {title}
Track:"""

    examples_str = "\n".join([f"Title: {ex['Title']}, Track: {ex['Track']}" for ex in examples])
    tracks_str = "\n".join([f"- {track}" for track in tracks])
    return PROMPT_TEMPLATE.format(examples=examples_str, title=title, tracks=tracks_str)

# Qwen API Interaction (Revised)
def get_qwen_prediction(prompt: str) -> str:
    try:
        # Use Generation.call with the recommended 'messages' format for chat models
        response = Generation.call(model='qwen-turbo-latest',
                            prompt=prompt,temperature=0.1
        )

        # Check for a successful response
        if response.status_code == HTTPStatus.OK:
            # The text content is in response.output.text
            return response.output.text
        else:
            # Print detailed error information if the call fails
            print(f"API call failed: request_id={response.request_id}, "
                  f"status_code={response.status_code}, code={response.code}, "
                  f"message={response.message}")
            return "Unknown"

    except Exception as e:
        print(f"An unexpected error occurred during the API call: {e}")
        return "Unknown"

# Main Classification and Evaluation Loop
def main():
    try:
        test_set, unique_tracks, few_shot_examples = load_data(INPUT_CSV_PATH)
        ground_truth = []
        predictions = []


        for _, row in tqdm(test_set.iterrows(), total=test_set.shape[0]):
            try:
                prompt = generate_prompt(row['Title'], few_shot_examples, unique_tracks)
                response_text = get_qwen_prediction(prompt)
                prediction = parse_response(response_text, unique_tracks)
                if prediction != "Unknown": # Only append if prediction is valid
                    ground_truth.append(row['Track Theme'])
                    predictions.append(prediction)

            except Exception as e:
                print(f"Error processing row: {str(e)}")
                predictions.append("Unknown")
                ground_truth.append(row['Track Theme'])

        # Get all unique classes from both predictions and ground truth
        pred_classes = sorted(list(set(predictions)))
        if "Unknown" in pred_classes:
            pred_classes.remove("Unknown")  # Remove Unknown from target names if present

        print(f"\nNumber of unique classes in predictions: {len(pred_classes)}")
        print(f"Number of unique classes in ground truth: {len(set(ground_truth))}")
        # Print deviation between prediction classes and ground truth classes
        gt_classes_set = set(ground_truth)
        pred_classes_set = set(predictions)
        only_in_gt = gt_classes_set - pred_classes_set
        only_in_pred = pred_classes_set - gt_classes_set

        print(f"Classes in ground truth but not in predictions: {only_in_gt}")
        print(f"Classes in predictions but not in ground truth: {only_in_pred}")

        # Calculate metrics
        accuracy = accuracy_score(ground_truth, predictions)
        micro_f1 = f1_score(ground_truth, predictions, average='micro')
        macro_f1 = f1_score(ground_truth, predictions, average='macro')

        print(f"\nAccuracy: {accuracy:.4f}")
        print(f"Micro F1: {micro_f1:.4f}")
        print(f"Macro F1: {macro_f1:.4f}")

        print("\nClassification Report:")
        print(classification_report(ground_truth, predictions, target_names=pred_classes))


        cm = ConfusionMatrixDisplay.from_predictions(ground_truth, predictions, display_labels=pred_classes, cmap=plt.cm.get_cmap('Blues'))
        plt.title("Confusion Matrix")
        plt.savefig("confusion_matrix.png")
        plt.close()

        report = classification_report(ground_truth, predictions, target_names=pred_classes, output_dict=False)
        with open("classification_report.txt", "w") as f:
            f.write(str(report))

    except Exception as e:
        print(f"Error in main execution: {str(e)}")
        sys.exit(1)

# Helper function to parse the model's response
def parse_response(response_text, tracks):
    for track in tracks:
        if track in response_text:
            return track
    return "Unknown"

if __name__ == "__main__":
    main()