def predict(payload):
    """Template prediction hook. Replace with real PyTorch inference."""
    return {
        "sample": "pytorch",
        "received": payload,
        "prediction": "replace_with_model_output",
    }
