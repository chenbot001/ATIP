import os
import pandas as pd
import joblib

# Paths to the model and data
MODEL_DIR = "c:/Eric/Projects/AI_Researcher_Network/classifier_models/tfidf"
DATA_PATH = "c:/Eric/Projects/AI_Researcher_Network/data/papers_data.csv"

# Load the pre-trained model, vectorizer, and label encoder
classifier = joblib.load(os.path.join(MODEL_DIR, "tfidf_classifier.joblib"))
tfidf_vectorizer = joblib.load(os.path.join(MODEL_DIR, "tfidf_vectorizer.joblib"))
label_encoder = joblib.load(os.path.join(MODEL_DIR, "label_encoder.joblib"))

def classify_papers():
    # Load the data
    print(f"Loading data from {DATA_PATH}...")
    df = pd.read_csv(DATA_PATH)

    # Check for required columns
    if 'title' not in df.columns or 'abstract' not in df.columns:
        raise ValueError("The dataset must contain 'title' and 'abstract' columns.")

    # Combine title and abstract into a single text input
    df['text_input'] = df.apply(
        lambda x: x['title'] + ' [SEP] ' + str(x['abstract']) if pd.notna(x['abstract']) else x['title'],
        axis=1
    )

    # Transform the text input using the TF-IDF vectorizer
    print("Transforming text input using the TF-IDF vectorizer...")
    features = tfidf_vectorizer.transform(df['text_input'])

    # Classify the papers
    print("Classifying papers...")
    predictions = classifier.predict(features)

    # Decode the predicted labels
    df['tracks'] = label_encoder.inverse_transform(predictions)

    # Remove the 'text_input' column as it is redundant
    df.drop(columns=['text_input'], inplace=True)

    # Save the updated DataFrame back to a CSV file
    output_path = DATA_PATH.replace(".csv", "_classified.csv")
    df.to_csv(output_path, index=False)
    print(f"Classification results saved to {output_path}")

if __name__ == "__main__":
    classify_papers()
