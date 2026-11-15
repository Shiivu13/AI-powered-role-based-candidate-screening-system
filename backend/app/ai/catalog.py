"""Static domain catalog: knowledge-base books, evaluation topics and job roles.

The catalog is the single source of truth that ties the three together:

* every **role** owns a set of **books** (its private knowledge base / vector
  collection) and a set of **topics** it may interview on;
* every **topic** carries the vocabulary used to (a) match it against a resume
  and (b) seed retrieval queries against the role's knowledge base.

Keeping this declarative (rather than asking an LLM "what should we ask about?")
makes interview planning deterministic, explainable and cheap. The LLM is used
where it adds real value: reading resumes and writing grounded questions.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Book:
    id: str
    title: str
    author: str
    filename: str
    url: str


@dataclass(frozen=True)
class Topic:
    id: str
    name: str
    description: str
    # Resume vocabulary: if any of these appear in the resume, the topic is
    # considered "anchored" in the candidate's background.
    keywords: tuple[str, ...]
    # Retrieval vocabulary: phrases that describe the topic the way a textbook
    # would. Used to build knowledge-base queries.
    retrieval_terms: tuple[str, ...]


@dataclass(frozen=True)
class Role:
    id: str
    title: str
    description: str
    book_ids: tuple[str, ...]
    topic_ids: tuple[str, ...]
    # Topics every candidate for this role should be probed on, regardless of
    # resume. Used to fill "gap" slots in the interview plan.
    core_topic_ids: tuple[str, ...]
    # Preferred question styles for this role, in priority order.
    question_styles: tuple[str, ...] = ("conceptual", "applied", "scenario")
    extra: dict = field(default_factory=dict)


BOOKS: dict[str, Book] = {
    b.id: b
    for b in [
        Book(
            "mitchell",
            "Machine Learning",
            "Tom Mitchell",
            "mitchell.pdf",
            "https://www.cs.cmu.edu/~tom/files/MachineLearningTomMitchell.pdf",
        ),
        Book(
            "burkov",
            "The Hundred-Page Machine Learning Book",
            "Andriy Burkov",
            "burkov.pdf",
            "https://ema.cri-info.cm/wp-content/uploads/2019/07/2019BurkovTheHundred-pageMachineLearning.pdf",
        ),
        Book(
            "ml_absolute_beginners",
            "Machine Learning for Absolute Beginners",
            "Oliver Theobald",
            "ml_absolute_beginners.pdf",
            "https://www.hlevkin.com/hlevkin/45MachineDeepLearning/ML/Machine%20Learning%20For%20Absolute%20Beginners.pdf",
        ),
        Book(
            "intro_ml_python",
            "Introduction to Machine Learning with Python",
            "Andreas C. Müller & Sarah Guido",
            "intro_ml_python.pdf",
            "https://www.nrigroupindia.com/e-book/Introduction%20to%20Machine%20Learning%20with%20Python%20%28%20PDFDrive.com%20%29-min.pdf",
        ),
        Book(
            "brownlee",
            "Master Machine Learning Algorithms",
            "Jason Brownlee",
            "brownlee.pdf",
            "https://raw.githubusercontent.com/khurrameycon/Data-Science-Books/main/Master%20Machine%20Learning%20Algorithms%20-%20Discover%20how%20they%20work%20and%20Implement%20Them%20From%20Scratch%20by%20Jason%20Brownlee%20%28z-lib.org%29.pdf",
        ),
        Book(
            "bishop",
            "Pattern Recognition and Machine Learning",
            "Christopher M. Bishop",
            "bishop.pdf",
            "https://www.microsoft.com/en-us/research/wp-content/uploads/2006/01/Bishop-Pattern-Recognition-and-Machine-Learning-2006.pdf",
        ),
        Book(
            "ai_ml_dl",
            "Artificial Intelligence, Machine Learning, and Deep Learning",
            "Oswald Campesato",
            "ai_ml_dl.pdf",
            "https://jcer.in/jcer-docs/E-Learning/Digital%20Library%20/E-Books/Artificial%20Intelligence%2C%20Machine%20Learning%2C%20and%20Deep%20Learning.pdf",
        ),
    ]
}


TOPICS: dict[str, Topic] = {
    t.id: t
    for t in [
        Topic(
            "supervised_fundamentals",
            "Supervised learning fundamentals",
            "Training/test split, hypothesis spaces, generalisation and inductive bias.",
            ("supervised learning", "classification", "regression", "machine learning", "scikit-learn", "sklearn", "predictive model"),
            ("supervised learning training data labels", "hypothesis space inductive bias generalization", "training set test set generalization"),
        ),
        Topic(
            "linear_models",
            "Linear & logistic regression",
            "Linear models, least squares, logistic regression and gradient descent.",
            ("linear regression", "logistic regression", "regression", "gradient descent", "glm", "statsmodels", "least squares"),
            ("linear regression least squares coefficients", "logistic regression sigmoid probability", "gradient descent learning rate cost function"),
        ),
        Topic(
            "decision_trees",
            "Decision trees",
            "Tree induction, splitting criteria, pruning.",
            ("decision tree", "cart", "id3", "random forest", "xgboost", "lightgbm", "catboost", "gradient boosting", "tree-based"),
            ("decision tree learning entropy information gain", "decision tree pruning overfitting", "classification and regression trees gini split"),
        ),
        Topic(
            "ensembles",
            "Ensemble methods",
            "Bagging, boosting, random forests and gradient boosting.",
            ("ensemble", "random forest", "xgboost", "lightgbm", "catboost", "boosting", "bagging", "adaboost", "gradient boosting", "stacking"),
            ("bagging bootstrap aggregation random forest", "boosting adaboost weak learners", "gradient boosted trees ensemble"),
        ),
        Topic(
            "neural_networks",
            "Neural networks & backpropagation",
            "Perceptrons, multilayer networks, activation functions and backpropagation.",
            ("neural network", "deep learning", "tensorflow", "pytorch", "keras", "backpropagation", "mlp", "perceptron", "ann"),
            ("artificial neural networks backpropagation algorithm", "perceptron gradient descent weights", "multilayer network hidden units activation function"),
        ),
        Topic(
            "deep_learning",
            "Deep learning architectures",
            "CNNs, RNNs/LSTMs, transformers, autoencoders and training deep nets.",
            ("cnn", "rnn", "lstm", "transformer", "bert", "gpt", "llm", "computer vision", "nlp", "convolutional", "pytorch", "tensorflow", "keras", "hugging face", "huggingface", "gan", "autoencoder"),
            ("convolutional neural network layers", "recurrent neural networks lstm sequence", "deep learning training dropout optimization"),
        ),
        Topic(
            "bayesian_learning",
            "Bayesian & probabilistic learning",
            "Bayes theorem, MAP/ML hypotheses, naive Bayes, Bayesian networks.",
            ("bayes", "bayesian", "naive bayes", "probabilistic", "probability", "statistics", "pymc", "mcmc"),
            ("bayes theorem maximum a posteriori hypothesis", "naive bayes classifier conditional independence", "maximum likelihood estimation probability"),
        ),
        Topic(
            "instance_based",
            "Instance-based learning (k-NN)",
            "Nearest neighbours, distance metrics and lazy learning.",
            ("knn", "k-nearest", "nearest neighbor", "nearest neighbour", "similarity search", "recommendation", "recommender"),
            ("k-nearest neighbor algorithm distance", "instance-based learning lazy learner", "distance metric euclidean neighbors"),
        ),
        Topic(
            "svm_kernels",
            "Support vector machines & kernels",
            "Maximum-margin classifiers, kernel trick, soft margins.",
            ("svm", "support vector", "kernel", "svc"),
            ("support vector machine maximum margin", "kernel trick feature space", "soft margin slack variables"),
        ),
        Topic(
            "unsupervised",
            "Clustering & unsupervised learning",
            "k-means, hierarchical clustering, density-based clustering.",
            ("clustering", "k-means", "kmeans", "unsupervised", "dbscan", "segmentation", "anomaly detection"),
            ("k-means clustering centroids", "unsupervised learning clustering algorithms", "hierarchical agglomerative clustering dbscan"),
        ),
        Topic(
            "dimensionality_reduction",
            "Dimensionality reduction",
            "PCA, manifold learning and feature extraction.",
            ("pca", "principal component", "dimensionality reduction", "t-sne", "tsne", "umap", "svd", "embeddings"),
            ("principal component analysis variance", "dimensionality reduction feature extraction", "manifold learning t-sne"),
        ),
        Topic(
            "evaluation",
            "Model evaluation & validation",
            "Cross-validation, metrics, confidence intervals, comparing learners.",
            ("cross-validation", "cross validation", "a/b test", "ab testing", "precision", "recall", "f1", "roc", "auc", "metrics", "evaluation", "mlflow", "experiment tracking"),
            ("cross-validation model evaluation", "precision recall confusion matrix roc", "evaluating hypotheses confidence intervals error estimation"),
        ),
        Topic(
            "bias_variance",
            "Overfitting, bias-variance & regularisation",
            "Overfitting, under-fitting, regularisation and model complexity.",
            ("overfitting", "regularization", "regularisation", "l1", "l2", "ridge", "lasso", "dropout", "bias-variance"),
            ("overfitting bias variance tradeoff", "regularization ridge lasso penalty", "model complexity underfitting overfitting"),
        ),
        Topic(
            "feature_engineering",
            "Data preprocessing & feature engineering",
            "Scaling, encoding, missing values, feature selection, pipelines.",
            ("pandas", "numpy", "feature engineering", "data cleaning", "etl", "preprocessing", "data pipeline", "sql", "spark", "data wrangling", "feature selection"),
            ("data preprocessing scaling normalization", "categorical variables one-hot encoding", "feature selection feature engineering"),
        ),
        Topic(
            "reinforcement_learning",
            "Reinforcement learning",
            "Q-learning, rewards, exploration vs exploitation.",
            ("reinforcement learning", "q-learning", "rl", "policy gradient", "openai gym", "gym", "reward"),
            ("reinforcement learning q learning reward", "exploration exploitation agent environment", "temporal difference learning policy"),
        ),
        Topic(
            "genetic_algorithms",
            "Genetic algorithms & search",
            "Evolutionary search, fitness functions, hypothesis-space search.",
            ("genetic algorithm", "evolutionary", "optimization", "heuristic search"),
            ("genetic algorithms fitness crossover mutation", "hypothesis space search evolution", "genetic programming population"),
        ),
        Topic(
            "probabilistic_graphical_models",
            "Graphical models & latent variables",
            "Bayesian networks, Markov random fields, mixture models and EM.",
            ("graphical model", "bayesian network", "hmm", "hidden markov", "mixture model", "gmm", "em algorithm", "latent variable", "variational"),
            ("graphical models bayesian networks conditional independence", "mixture of gaussians em algorithm", "hidden markov models latent variables"),
        ),
        Topic(
            "kernel_methods_gp",
            "Kernel methods & Gaussian processes",
            "Kernels, Gaussian processes, sparse kernel machines.",
            ("gaussian process", "kernel", "rbf", "svm", "relevance vector"),
            ("gaussian processes kernel functions", "sparse kernel machines relevance vector", "kernel methods dual representation"),
        ),
        Topic(
            "ai_foundations",
            "AI foundations & applied AI",
            "Classic AI, NLP, chatbots and the AI/ML/DL landscape.",
            ("artificial intelligence", "ai", "nlp", "chatbot", "natural language", "llm", "generative ai", "genai", "langchain", "rag"),
            ("artificial intelligence machine learning deep learning overview", "natural language processing tasks", "chatbots and conversational AI"),
        ),
    ]
}


ROLES: dict[str, Role] = {
    r.id: r
    for r in [
        Role(
            id="ai_ml_engineer",
            title="AI / ML Engineer",
            description="Builds and ships learning systems end to end: core ML theory, model families and evaluation.",
            book_ids=("mitchell", "burkov", "ml_absolute_beginners"),
            topic_ids=(
                "supervised_fundamentals", "linear_models", "decision_trees", "ensembles",
                "neural_networks", "bayesian_learning", "instance_based", "svm_kernels",
                "unsupervised", "evaluation", "bias_variance", "reinforcement_learning",
                "genetic_algorithms", "feature_engineering",
            ),
            core_topic_ids=("supervised_fundamentals", "evaluation", "bias_variance", "neural_networks", "decision_trees"),
            question_styles=("conceptual", "applied", "scenario"),
        ),
        Role(
            id="data_scientist",
            title="Data Scientist / Applied ML",
            description="Turns data into models with Python tooling: preprocessing, algorithm choice and validation.",
            book_ids=("intro_ml_python", "brownlee"),
            topic_ids=(
                "supervised_fundamentals", "linear_models", "decision_trees", "ensembles",
                "instance_based", "svm_kernels", "unsupervised", "dimensionality_reduction",
                "evaluation", "bias_variance", "feature_engineering", "neural_networks",
                "bayesian_learning",
            ),
            core_topic_ids=("feature_engineering", "evaluation", "linear_models", "ensembles", "bias_variance"),
            question_styles=("applied", "scenario", "conceptual"),
        ),
        Role(
            id="ml_research",
            title="ML Research / Theoretical ML",
            description="Deep, mathematical understanding of probabilistic models and modern deep learning.",
            book_ids=("bishop", "ai_ml_dl"),
            topic_ids=(
                "bayesian_learning", "linear_models", "neural_networks", "deep_learning",
                "probabilistic_graphical_models", "kernel_methods_gp", "svm_kernels",
                "unsupervised", "dimensionality_reduction", "bias_variance", "ai_foundations",
            ),
            core_topic_ids=("bayesian_learning", "probabilistic_graphical_models", "bias_variance", "neural_networks"),
            question_styles=("conceptual", "derivation", "scenario"),
        ),
    ]
}


def get_role(role_id: str) -> Role | None:
    return ROLES.get(role_id)


def role_topics(role: Role) -> list[Topic]:
    return [TOPICS[t] for t in role.topic_ids]


def role_books(role: Role) -> list[Book]:
    return [BOOKS[b] for b in role.book_ids]
