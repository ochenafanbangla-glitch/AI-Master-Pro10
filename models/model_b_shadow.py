import random

class ModelBShadow:
    """
    Model B (Son): Shadow learner that learns from Model A's mistakes.
    """
    def __init__(self):
        self.name = "Model B (Son)"
        self.error_log = []

    def shadow_predict(self, model_a_prediction):
        # Model B might predict differently based on its "learning"
        # For now, it's a variation of Model A
        if random.random() > 0.8:
            prediction = "SMALL" if model_a_prediction == "BIG" else "BIG"
        else:
            prediction = model_a_prediction
            
        return {
            "prediction": prediction,
            "confidence": round(random.uniform(60, 95), 2)
        }

    def learn_from_error(self, trade_id, model_a_prediction, actual_result):
        if model_a_prediction != actual_result:
            self.error_log.append({
                "trade_id": trade_id,
                "predicted": model_a_prediction,
                "actual": actual_result
            })
            # In a real scenario, this would trigger a weight update
            return True
        return False

    def forget_error(self, trade_id):
        """
        Removes a specific error from Model B's shadow learning log.
        """
        initial_len = len(self.error_log)
        self.error_log = [e for e in self.error_log if e.get('trade_id') != trade_id]
        return len(self.error_log) < initial_len
