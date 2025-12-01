"""
Unit Tests for Cryptography Layer
Tests key generation, signing, verification, and hashing
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from crypto.keys import KeyPair
from crypto.signature import SignedMessage
from crypto.hashing import hash_data, hash_dict, hash_dict_hex
import base64


def _crypto_diagnostics(label: str, **kwargs):
    """Print helpful diagnostics for crypto tests.

    Accepts keyword arguments for items to display (keys, signatures, hashes, dicts).
    """
    print("\n" + "#" * 60)
    print(f"CRYPTO DIAGNOSTICS: {label}")
    print("#" * 60)
    # Print keys
    if "keypair" in kwargs and kwargs["keypair"] is not None:
        kp = kwargs["keypair"]
        try:
            pub = kp.get_public_key_bytes()
            print(f" public_key (base64): {base64.b64encode(pub).decode()}")
            print(f" public_key_len: {len(pub)} bytes")
            print(f" address: {kp.get_address()}")
        except Exception as e:
            print(f"  (key print error) {e}")

    # Print signature bytes
    if "signature" in kwargs and kwargs["signature"] is not None:
        sig = kwargs["signature"]
        try:
            print(f" signature (base64): {base64.b64encode(sig).decode()}")
            print(f" signature_len: {len(sig)} bytes")
        except Exception as e:
            print(f"  (sig print error) {e}")

    # Print other string/blobs
    if "signature_b64" in kwargs:
        print(f" signature_b64 (provided): {kwargs['signature_b64']}")

    # Print hashes
    if "hashes" in kwargs and kwargs["hashes"]:
        for k, v in kwargs["hashes"].items():
            print(f" {k}: {v}")

    # Print serialized dicts
    if "dict" in kwargs and kwargs["dict"] is not None:
        d = kwargs["dict"]
        print(f" dict keys: {list(d.keys())}")
        # show truncated view
        for kk, vv in list(d.items())[:8]:
            print(f"  {kk}: {str(vv)[:120]}")

    # Print booleans / statuses
    for k, v in kwargs.items():
        if k in ("keypair", "signature", "hashes", "dict", "signature_b64"):
            continue
        print(f" {k}: {v}")


def test_keypair_generation():
    """Test that keypairs are generated correctly"""
    print("\nTEST: KeyPair Generation")
    
    keypair1 = KeyPair()
    keypair2 = KeyPair()
    
    # Different keypairs should have different addresses
    assert keypair1.get_address() != keypair2.get_address(), \
        "Two keypairs generated the same address"
    
    # Address should be base64 encoded
    try:
        decoded = base64.b64decode(keypair1.get_address())
        assert len(decoded) == 32, "Public key should be 32 bytes"
    except Exception as e:
        raise AssertionError(f"Address is not valid base64: {e}")
    # Diagnostics: show key info
    _crypto_diagnostics("keypair_generation", keypair=keypair1)

    print("PASSED: KeyPair generation works correctly")
    return True

def test_signature_verification():
    """Test signing and verification"""
    print("\nTEST: Signature Verification")
    
    keypair = KeyPair()
    message = b"Hello, blockchain!"
    
    # Sign message
    signature = keypair.sign(message)
    
    # Verify with correct key
    is_valid = KeyPair.verify(
        keypair.get_public_key_bytes(),
        signature,
        message
    )
    assert is_valid, "Valid signature was rejected"
    
    # Verify with wrong message
    wrong_message = b"Different message"
    is_valid = KeyPair.verify(
        keypair.get_public_key_bytes(),
        signature,
        wrong_message
    )
    assert not is_valid, "Invalid signature was accepted (wrong message)"
    
    # Verify with wrong key
    other_keypair = KeyPair()
    is_valid = KeyPair.verify(
        other_keypair.get_public_key_bytes(),
        signature,
        message
    )
    assert not is_valid, "Invalid signature was accepted (wrong key)"
    # Diagnostics: show signature and verification results
    _crypto_diagnostics("signature_verification", keypair=keypair, signature=signature,
                        verified_correct=is_valid)

    print("PASSED: Signature verification works correctly")
    return True

def test_domain_separation():
    """Test that domain separation prevents signature reuse"""
    print("\nTEST: Domain Separation")
    
    keypair = KeyPair()
    chain_id = "test-chain"
    data = {"value": 42}
    
    # Create and sign a transaction message
    tx_msg = SignedMessage(SignedMessage.DOMAIN_TX, chain_id, data)
    tx_msg.sign(keypair)
    
    # Create a vote message with same data
    vote_msg = SignedMessage(SignedMessage.DOMAIN_VOTE, chain_id, data)
    vote_msg.signature = tx_msg.signature  # Try to reuse signature
    
    # Verification should fail because domains are different
    is_valid = vote_msg.verify(keypair.get_public_key_bytes())
    assert not is_valid, "Signature was reused across different domains"
    
    # Sign vote message properly
    vote_msg.sign(keypair)
    is_valid = vote_msg.verify(keypair.get_public_key_bytes())
    assert is_valid, "Valid vote signature was rejected"
    
    # The two signatures should be different
    assert tx_msg.signature != vote_msg.signature, \
        "Different domains produced the same signature"
    # Diagnostics: show both signatures and domain verification
    _crypto_diagnostics("domain_separation",
                        keypair=keypair,
                        tx_signature=tx_msg.signature,
                        vote_signature=vote_msg.signature,
                        tx_sig_b64=base64.b64encode(tx_msg.signature).decode(),
                        vote_sig_b64=base64.b64encode(vote_msg.signature).decode(),
                        tx_verified=SignedMessage.from_dict(tx_msg.to_dict()).verify(keypair.get_public_key_bytes()),
                        vote_verified=SignedMessage.from_dict(vote_msg.to_dict()).verify(keypair.get_public_key_bytes()))
    
    print("PASSED: Domain separation prevents signature reuse")
    return True

def test_deterministic_hashing():
    """Test that hashing is deterministic"""
    print("\nTEST: Deterministic Hashing")
    
    data = {
        "height": 10,
        "parent": "abc123",
        "transactions": ["tx1", "tx2", "tx3"]
    }
    
    # Hash multiple times
    hash1 = hash_dict_hex(data)
    hash2 = hash_dict_hex(data)
    hash3 = hash_dict_hex(data)
    
    assert hash1 == hash2 == hash3, \
        "Same data produced different hashes"
    
    # Different order should produce same hash (sorted keys)
    data_reordered = {
        "transactions": ["tx1", "tx2", "tx3"],
        "parent": "abc123",
        "height": 10
    }
    hash4 = hash_dict_hex(data_reordered)
    assert hash1 == hash4, \
        "Key reordering produced different hash"
    
    # Different data should produce different hash
    data_modified = data.copy()
    data_modified["height"] = 11
    hash5 = hash_dict_hex(data_modified)
    assert hash1 != hash5, \
        "Different data produced same hash"
    # Diagnostics: show hashes
    _crypto_diagnostics("deterministic_hashing", hashes={
        "hash1": hash1,
        "hash4": hash4,
        "hash5": hash5
    })

    print("PASSED: Hashing is deterministic and collision-resistant")
    return True

def test_chain_id_separation():
    """Test that different chain IDs produce different signatures"""
    print("\nTEST: Chain ID Separation")
    
    keypair = KeyPair()
    data = {"amount": 100, "recipient": "alice"}
    
    # Sign with chain_id_1
    msg1 = SignedMessage(SignedMessage.DOMAIN_TX, "chain-1", data)
    msg1.sign(keypair)
    
    # Sign with chain_id_2
    msg2 = SignedMessage(SignedMessage.DOMAIN_TX, "chain-2", data)
    msg2.sign(keypair)
    
    # Signatures should be different
    assert msg1.signature != msg2.signature, \
        "Different chain IDs produced same signature"
    
    # Signature from chain-1 shouldn't verify for chain-2
    msg1_on_chain2 = SignedMessage(SignedMessage.DOMAIN_TX, "chain-2", data)
    msg1_on_chain2.signature = msg1.signature
    is_valid = msg1_on_chain2.verify(keypair.get_public_key_bytes())
    assert not is_valid, \
        "Signature was reused across different chains"
    
    print("PASSED: Chain ID separation prevents cross-chain replay")
    return True

def test_serialization():
    """Test that signed messages can be serialized and deserialized"""
    print("\nTEST: Message Serialization")
    
    keypair = KeyPair()
    chain_id = "test-chain"
    data = {"key": "value", "number": 123}
    
    # Create and sign message
    original = SignedMessage(SignedMessage.DOMAIN_TX, chain_id, data)
    original.sign(keypair)
    
    # Serialize to dict
    serialized = original.to_dict()
    
    # Deserialize
    restored = SignedMessage.from_dict(serialized)
    
    # Verify all fields match
    assert restored.domain == original.domain
    assert restored.chain_id == original.chain_id
    assert restored.data == original.data
    assert restored.signature == original.signature
    assert restored.signer_address == original.signer_address
    
    # Verify signature still valid
    is_valid = restored.verify(keypair.get_public_key_bytes())
    assert is_valid, "Deserialized signature is invalid"
    # Diagnostics: show serialized dict and signature b64
    _crypto_diagnostics("serialization",
                        keypair=keypair,
                        dict=serialized,
                        signature=original.signature,
                        signature_b64=base64.b64encode(original.signature).decode())

    print("PASSED: Message serialization preserves integrity")
    return True

def test_tamper_detection():
    """Test that tampering with signed data is detected"""
    print("\nTEST: Tamper Detection")
    
    keypair = KeyPair()
    chain_id = "test-chain"
    data = {"amount": 100}
    
    # Create and sign
    msg = SignedMessage(SignedMessage.DOMAIN_TX, chain_id, data)
    msg.sign(keypair)
    
    # Store original signature
    original_signature = msg.signature
    
    # Tamper with data
    msg.data["amount"] = 1000
    msg.signature = original_signature  # Keep old signature
    
    # Verification should fail
    is_valid = msg.verify(keypair.get_public_key_bytes())
    assert not is_valid, "Tampered data was not detected"
    # Diagnostics: show original and tampered signature/verification
    _crypto_diagnostics("tamper_detection",
                        keypair=keypair,
                        original_signature=original_signature,
                        tampered_signature=msg.signature,
                        original_sig_b64=base64.b64encode(original_signature).decode())

    print("PASSED: Data tampering is detected")
    return True

def run_all_crypto_tests():
    """Run all cryptography tests"""
    print("\n" + "="*80)
    print("RUNNING CRYPTOGRAPHY UNIT TESTS")
    print("="*80)
    
    tests = [
        test_keypair_generation,
        test_signature_verification,
        test_domain_separation,
        test_deterministic_hashing,
        test_chain_id_separation,
        test_serialization,
        test_tamper_detection
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append((test_func.__name__, result))
        except Exception as e:
            print(f"FAILED: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_func.__name__, False))
    
    print("\n" + "="*80)
    print("CRYPTOGRAPHY TEST SUMMARY")
    print("="*80)
    
    for name, result in results:
        status = "PASSED" if result else "FAILED"
        print(f"{status}: {name}")
    
    all_passed = all(r for _, r in results)
    
    if all_passed:
        print("\nALL CRYPTOGRAPHY TESTS PASSED!")
        return 0
    else:
        print("\nSOME TESTS FAILED")
        return 1

if __name__ == "__main__":
    exit_code = run_all_crypto_tests()
    sys.exit(exit_code)