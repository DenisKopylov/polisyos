"""Print the full actual typed method binding vocabulary for a deciding receipt."""
import json
from tools.quality.validation.check_layer3_gy_phase2_artifacts import recompute_foundry_binding_vocabulary

def main():
    print("C3_VOCABULARY=" + json.dumps(recompute_foundry_binding_vocabulary(), sort_keys=True))

if __name__ == "__main__": main()
