"""A tiny synthetic textbook used to build an isolated test knowledge base."""

SECTIONS = {
    "3.1 Decision Tree Learning": [
        "Decision tree learning is a method for approximating discrete-valued target functions, in which the learned function is represented by a decision tree. Each internal node tests an attribute and each branch corresponds to one of the possible values for this attribute.",
        "The ID3 algorithm grows the tree top-down, selecting at each node the attribute that best classifies the training examples. The best attribute is the one with the highest information gain, which is the expected reduction in entropy caused by partitioning the examples on that attribute.",
        "Entropy characterizes the impurity of an arbitrary collection of examples. Information gain measures how well a given attribute separates the training examples according to their target classification, and is used to choose among candidate attributes at each step.",
        "Decision trees are prone to overfitting the training data when the tree grows until it perfectly classifies every example. Reduced error pruning and rule post-pruning remove nodes whose removal does not hurt accuracy on a separate validation set.",
    ],
    "4.2 Overfitting And The Bias Variance Tradeoff": [
        "A hypothesis overfits the training examples if some other hypothesis that fits the training examples less well actually performs better over the entire distribution of instances. Overfitting is a significant practical difficulty for decision tree learning and neural networks.",
        "Bias is the error from overly simple assumptions in the model, while variance is the error from sensitivity to small fluctuations in the training set. Increasing model complexity typically reduces bias but increases variance, which is the bias variance tradeoff.",
        "Regularization adds a penalty on model complexity to the loss function. Ridge regression penalizes the squared magnitude of the coefficients while lasso penalizes their absolute values, which drives some coefficients to exactly zero and performs feature selection.",
    ],
    "4.5 Artificial Neural Networks And Backpropagation": [
        "Artificial neural networks provide a general method for learning real-valued and vector-valued functions from examples. A multilayer network contains hidden units whose sigmoid activation functions allow the network to represent nonlinear decision surfaces.",
        "The backpropagation algorithm learns the weights of a multilayer network using gradient descent to minimize the squared error between the network outputs and the target values. Error terms are propagated backwards from the output units to the hidden units using the chain rule.",
        "The learning rate controls the size of each weight update in gradient descent. A momentum term can help the search escape small local minima and speeds convergence along flat regions of the error surface.",
    ],
    "5.3 Evaluating Hypotheses With Cross Validation": [
        "Cross validation estimates how well a learned hypothesis will generalize to unseen data. In k-fold cross validation the data is partitioned into k disjoint subsets, and each subset is used once as the test set while the remaining subsets are used for training.",
        "Precision is the fraction of positive predictions that are correct, while recall is the fraction of actual positives that were found. The ROC curve plots the true positive rate against the false positive rate across decision thresholds and the area under it summarizes ranking quality.",
        "Confidence intervals for the true error of a hypothesis can be computed from the sample error, because the number of errors over a random sample follows a binomial distribution that is well approximated by a normal distribution for large samples.",
    ],
    "6.2 Bayes Theorem And Naive Bayes": [
        "Bayes theorem provides a way to calculate the posterior probability of a hypothesis given the observed data from its prior probability and the likelihood of the data. The maximum a posteriori hypothesis is the most probable hypothesis given the data.",
        "The naive Bayes classifier assumes the attribute values are conditionally independent given the target value. Despite this simplifying assumption it performs well in many practical domains such as text classification and spam filtering.",
    ],
    "7.1 Ensemble Methods Bagging And Boosting": [
        "Bagging trains each model in the ensemble on a bootstrap sample of the training data and averages their predictions, which mainly reduces variance. Random forests add randomness by considering a random subset of features at each split of each tree.",
        "Boosting trains weak learners sequentially, with each new learner focusing on the examples the previous learners misclassified. Gradient boosting fits each new tree to the negative gradient of the loss function of the current ensemble, mainly reducing bias.",
        "The number of boosting rounds and the learning rate interact: a smaller learning rate requires more trees but usually generalizes better. Early stopping on a validation set prevents gradient boosting from overfitting.",
    ],
    "8.1 Data Preprocessing And Feature Engineering": [
        "Many algorithms are sensitive to the scale of the features. Standard scaling transforms each feature to have zero mean and unit variance, while min max scaling shifts and rescales each feature to lie between zero and one.",
        "Categorical variables are commonly converted with one-hot encoding, which replaces a feature with several binary features, one per category. Scaling and encoding should be fitted on the training data only and then applied to the test data to avoid data leakage.",
    ],
    "9.1 Clustering With K-Means": [
        "The k-means algorithm partitions the data into k clusters by alternating between assigning each point to its nearest cluster center and recomputing each center as the mean of the points assigned to it, which decreases the within-cluster sum of squares.",
        "Principal component analysis finds orthogonal directions of maximum variance in the data. Projecting onto the leading principal components is a common dimensionality reduction technique applied before clustering or visualization.",
    ],
}


def corpus_pages():
    from app.rag.loaders import Page

    pages = []
    for number, (heading, paragraphs) in enumerate(SECTIONS.items(), start=1):
        text = heading + "\n" + "\n".join(paragraphs)
        pages.append(Page(number, text))
    return pages
