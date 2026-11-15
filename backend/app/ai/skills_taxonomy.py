"""Skill taxonomy used for deterministic resume parsing.

Maps canonical skill names to aliases and a category. Deterministic matching
gives reliable, explainable signals (and works offline); the LLM extractor
adds whatever the taxonomy does not know about.
"""
from __future__ import annotations

SKILLS: dict[str, dict] = {
    # Programming languages
    "Python": {"aliases": ["python", "python3"], "category": "language"},
    "R": {"aliases": [r"\bR\b(?=\s*(?:,|/|\)|programming|language|studio))", r"\bRStudio\b"], "category": "language", "regex": True, "case_sensitive": True},
    "Java": {"aliases": [r"\bjava\b(?!script)"], "category": "language", "regex": True},
    "Scala": {"aliases": ["scala"], "category": "language"},
    "C++": {"aliases": ["c++", "cpp"], "category": "language"},
    "Go": {"aliases": ["golang"], "category": "language"},
    "JavaScript": {"aliases": ["javascript", "typescript", "node.js", "nodejs"], "category": "language"},
    "SQL": {"aliases": ["sql", "postgresql", "postgres", "mysql", "sqlite", "t-sql", "pl/sql"], "category": "data"},
    "Julia": {"aliases": ["julia"], "category": "language"},
    "MATLAB": {"aliases": ["matlab"], "category": "language"},
    # ML / DS libraries
    "scikit-learn": {"aliases": ["scikit-learn", "sklearn", "scikit learn"], "category": "ml_framework"},
    "TensorFlow": {"aliases": ["tensorflow", "tf.keras"], "category": "ml_framework"},
    "PyTorch": {"aliases": ["pytorch", "torch"], "category": "ml_framework"},
    "Keras": {"aliases": ["keras"], "category": "ml_framework"},
    "XGBoost": {"aliases": ["xgboost"], "category": "ml_framework"},
    "LightGBM": {"aliases": ["lightgbm"], "category": "ml_framework"},
    "CatBoost": {"aliases": ["catboost"], "category": "ml_framework"},
    "Hugging Face": {"aliases": ["hugging face", "huggingface", "transformers library"], "category": "ml_framework"},
    "LangChain": {"aliases": ["langchain", "llamaindex", "llama index"], "category": "ml_framework"},
    "pandas": {"aliases": ["pandas"], "category": "data"},
    "NumPy": {"aliases": ["numpy"], "category": "data"},
    "SciPy": {"aliases": ["scipy"], "category": "data"},
    "Matplotlib/Seaborn": {"aliases": ["matplotlib", "seaborn", "plotly"], "category": "data"},
    "Spark": {"aliases": ["spark", "pyspark", "databricks"], "category": "data"},
    "Airflow": {"aliases": ["airflow"], "category": "mlops"},
    "MLflow": {"aliases": ["mlflow", "weights & biases", "wandb"], "category": "mlops"},
    "Docker": {"aliases": ["docker", "kubernetes", "k8s"], "category": "mlops"},
    "AWS": {"aliases": ["aws", "sagemaker", "amazon web services"], "category": "cloud"},
    "GCP": {"aliases": ["gcp", "google cloud", "vertex ai", "bigquery"], "category": "cloud"},
    "Azure": {"aliases": ["azure"], "category": "cloud"},
    "FastAPI/Flask": {"aliases": ["fastapi", "flask", "django"], "category": "backend"},
    "Vector databases": {"aliases": ["faiss", "chromadb", "chroma", "pinecone", "weaviate", "qdrant", "milvus", "pgvector"], "category": "ml_framework"},
    "OpenCV": {"aliases": ["opencv"], "category": "ml_framework"},
    # ML concepts
    "Machine learning": {"aliases": ["machine learning", "ml models", "ml engineer"], "category": "ml_concept"},
    "Deep learning": {"aliases": ["deep learning", "neural network", "neural networks"], "category": "ml_concept"},
    "NLP": {"aliases": ["nlp", "natural language processing", "text classification", "named entity", "sentiment analysis"], "category": "ml_concept"},
    "Computer vision": {"aliases": ["computer vision", "image classification", "object detection", "segmentation", "cnn", "yolo"], "category": "ml_concept"},
    "LLMs / GenAI": {"aliases": ["llm", "large language model", "gpt", "generative ai", "genai", "prompt engineering", "rag", "retrieval-augmented", "fine-tuning", "fine tuning", "bert"], "category": "ml_concept"},
    "Transformers": {"aliases": ["transformer", "attention mechanism", "self-attention"], "category": "ml_concept"},
    "RNN/LSTM": {"aliases": ["rnn", "lstm", "gru", "sequence model"], "category": "ml_concept"},
    "Reinforcement learning": {"aliases": ["reinforcement learning", "q-learning", "policy gradient"], "category": "ml_concept"},
    "Regression": {"aliases": ["linear regression", "logistic regression", "regression analysis", "regression model"], "category": "ml_concept"},
    "Classification": {"aliases": ["classification", "classifier"], "category": "ml_concept"},
    "Clustering": {"aliases": ["clustering", "k-means", "kmeans", "dbscan", "customer segmentation"], "category": "ml_concept"},
    "Decision trees / ensembles": {"aliases": ["decision tree", "random forest", "gradient boosting", "ensemble", "bagging", "adaboost"], "category": "ml_concept"},
    "SVM": {"aliases": ["svm", "support vector"], "category": "ml_concept"},
    "Bayesian methods": {"aliases": ["bayesian", "naive bayes", "bayes", "mcmc", "probabilistic model"], "category": "ml_concept"},
    "Dimensionality reduction": {"aliases": ["pca", "principal component", "dimensionality reduction", "t-sne", "umap"], "category": "ml_concept"},
    "Feature engineering": {"aliases": ["feature engineering", "feature selection", "data preprocessing", "data cleaning"], "category": "ml_concept"},
    "Model evaluation": {"aliases": ["cross-validation", "cross validation", "a/b test", "ab test", "hyperparameter tuning", "grid search", "precision", "recall", "roc", "auc", "f1-score", "f1 score"], "category": "ml_concept"},
    "Time series": {"aliases": ["time series", "forecasting", "arima", "prophet"], "category": "ml_concept"},
    "Recommender systems": {"aliases": ["recommender", "recommendation system", "collaborative filtering"], "category": "ml_concept"},
    "Statistics": {"aliases": ["statistics", "statistical", "hypothesis testing", "probability"], "category": "ml_concept"},
    "MLOps": {"aliases": ["mlops", "model deployment", "model serving", "ci/cd"], "category": "mlops"},
}

DOMAINS: dict[str, list[str]] = {
    "Finance / FinTech": ["finance", "fintech", "banking", "credit", "fraud", "trading", "loan", "insurance"],
    "Healthcare": ["healthcare", "medical", "clinical", "patient", "hospital", "radiology", "biomedical"],
    "E-commerce / Retail": ["e-commerce", "ecommerce", "retail", "customer churn", "recommendation", "shopping", "marketing"],
    "Natural language": ["chatbot", "nlp", "text", "language model", "sentiment"],
    "Computer vision": ["image", "video", "vision", "camera", "detection"],
    "Telecom / IoT": ["telecom", "iot", "sensor", "network traffic"],
    # Not "education": every resume has an EDUCATION section header.
    "Education / EdTech": ["edtech", "e-learning", "student performance", "learning platform", "online courses"],
    "Autonomous systems / Robotics": ["robot", "autonomous", "self-driving", "drone"],
    "Research / Academia": ["research", "publication", "thesis", "paper", "conference"],
}
