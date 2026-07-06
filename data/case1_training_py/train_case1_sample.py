from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split


def main():
    iris = load_iris(as_frame=True)
    x_train, x_test, y_train, y_test = train_test_split(
        iris.data,
        iris.target,
        test_size=0.2,
        random_state=42,
    )

    model = LogisticRegression(max_iter=200)
    model.fit(x_train, y_train)
    _ = model.predict(x_test)


if __name__ == "__main__":
    main()
