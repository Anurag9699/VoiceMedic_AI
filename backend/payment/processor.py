import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Setup audit log directory
BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_LOG_FILE = LOG_DIR / "audit_log.jsonl"

def execute_payment(parsed_command: Dict[str, Any], speaker_verification: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes a simulated payment based on the parsed command and speaker verification.
    Logs the transaction to an audit file.
    """
    # 1. Validation
    is_valid_command = parsed_command.get("is_valid", False)
    is_verified_speaker = speaker_verification.get("verified", False)
    
    status = "FAILED"
    reason = None
    transaction_id = str(uuid.uuid4())
    
    pin = parsed_command.get("entities", {}).get("pin")
    amount = parsed_command.get("entities", {}).get("amount", 0)
    
    # Load current balance
    wallet_file = LOG_DIR / "wallet.json"
    if not wallet_file.exists():
        with open(wallet_file, "w") as f:
            json.dump({"balance": 1000}, f)
    
    with open(wallet_file, "r") as f:
        wallet = json.load(f)
    current_balance = wallet.get("balance", 1000)
    
    if not is_valid_command:
        reason = "Invalid or unrecognized command intent."
    elif not is_verified_speaker:
        reason = "Speaker verification failed. Unauthorized."
    elif not pin:
        status = "PIN_REQUIRED"
        reason = "Please provide your 4-digit PIN to confirm."
    elif pin != "1234":  # Hardcoded PIN for the prototype
        reason = "Incorrect PIN."
    elif amount > current_balance:
        reason = "Insufficient funds."
    else:
        # All checks passed
        status = "SUCCESS"
        reason = "Payment executed successfully."
        # Deduct balance
        wallet["balance"] = current_balance - amount
        with open(wallet_file, "w") as f:
            json.dump(wallet, f)
        
    # 2. Construct Receipt
    receipt = {
        "transaction_id": transaction_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "status": status,
        "reason": reason,
        "amount": amount,
        "currency": parsed_command.get("entities", {}).get("currency"),
        "payee": parsed_command.get("entities", {}).get("payee"),
        "payer_id": speaker_verification.get("user_id", "unknown"),
        "new_balance": wallet.get("balance", current_balance)
    }
    
    # 3. Write to Audit Log
    try:
        with open(AUDIT_LOG_FILE, "a") as f:
            f.write(json.dumps(receipt) + "\n")
    except Exception as e:
        receipt["audit_log_error"] = str(e)
        
    return receipt
