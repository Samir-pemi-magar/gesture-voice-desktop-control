import pandas as pd
import pickle
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report

df = pd.read_csv('gesture_data.csv', header=None)
X = df.iloc[:, :-1].values
y = df.iloc[:, -1].values

print(f"Total samples: {len(df)}")
print(f"Samples per gesture:\n{df.iloc[:, -1].value_counts()}")

le = LabelEncoder()
y_encoded = le.fit_transform(y)

X_train, X_test, y_train, y_test = train_test_split(
    X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
)

pipeline = Pipeline([
    ('scaler', StandardScaler()),
    ('model', MLPClassifier(
        hidden_layer_sizes=(64, 32),
        max_iter=1000,
        random_state=42,
        early_stopping=True,
        verbose=True,
    ))
])
pipeline.fit(X_train, y_train)

y_pred = pipeline.predict(X_test)
print("\n--- Results ---")
print(classification_report(y_test, y_pred, target_names=le.classes_))

with open('gesture_model.pkl', 'wb') as f:
    pickle.dump((pipeline, le), f)

print("Saved gesture_model.pkl")