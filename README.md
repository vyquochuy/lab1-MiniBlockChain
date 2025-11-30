# 🔗 Minimal Layer 1 Blockchain

Một blockchain Layer 1 tối thiểu được thiết kế để đạt được độ cuối cùng (finality) đáng tin cậy trong môi trường mạng không đáng tin cậy.

## Tính năng chính

- **Two-Phase Consensus** (Prevote → Precommit)
- **Deterministic Execution** - Cùng input → cùng output
- **Unreliable Network Simulation** - Delays, packet loss, reordering
- **Cryptographic Security** - Ed25519 signatures, SHA-256 hashing
- **Domain Separation** - Chống signature replay attacks
- **Rate Limiting** - Giới hạn tốc độ gửi messages
- **Comprehensive Tests** - 40 unit tests + 4 E2E tests

## Cấu trúc thư mục
```
project/
├── src/
│   ├── crypto/          # Lớp mật mã học (keys, signatures, hashing)
│   ├── execution/       # Lớp thực thi (state, transactions, executor)
│   ├── consensus/       # Lớp đồng thuận (blocks, votes, consensus)
│   ├── network/         # Lớp mạng (network simulation, messages)
│   ├── node.py          # Full blockchain node
│   └── run_simulation.py # Main simulation runner
├── tests/               # Test suites
│   ├── test_crypto.py
│   ├── test_execution.py
│   ├── test_consensus.py
│   ├── test_network.py
│   ├── test_e2e.py
│   └── run_all_test.py
├── config/
│   └── config.json      # Configuration file
└── logs/                # Log outputs
```

## Cài đặt

### 1. Yêu cầu hệ thống

- Python 3.8+
- pip

### 2. Cài đặt dependencies
```bash
pip install cryptography
```


## Chạy chương trình

### 1. Chạy simulation blockchain
```bash
cd src
python run_simulation.py
```

### 2. Chạy tất cả tests
```bash
cd tests
python run_all_test.py
```

### 3. Chạy từng test suite riêng lẻ
```bash
# Test cryptography
python tests/test_crypto.py

# Test execution layer
python tests/test_execution.py

# Test consensus
python tests/test_consensus.py

# Test network
python tests/test_network.py

# Test end-to-end
python tests/test_e2e.py
```

## Xem logs

Logs được lưu trong thư mục `logs/`:


## Các khái niệm cốt lõi

### State (Trạng thái)
- Key-value store lưu trữ balances
- Deterministic hashing
- Copy mechanism cho isolation

### Transaction (Giao dịch)
- Signed với Ed25519
- Nonce-based replay protection
- Domain separation: `TX:chain_id`

### Block (Khối)
- Header: height, parent_hash, state_hash, tx_root
- Body: ordered list of transactions
- Finalization với > 2/3 votes

### Vote (Bầu chọn)
- Two phases: Prevote và Precommit
- Domain separation: `VOTE:chain_id`
- Majority: > 2/3 validators

### Consensus (Đồng thuận)
```
PROPOSE → PREVOTE → PRECOMMIT → FINALIZE
          (>2/3)    (>2/3)
```

## Security Features

- **Ed25519 Signatures** - Fast và secure
- **SHA-256 Hashing** - Collision-resistant
- **Domain Separation** - Chống replay attacks
- **Nonce Tracking** - Chống transaction replay
- **Rate Limiting** - Chống spam/DoS

## Network Simulation

Mạng mô phỏng các điều kiện thực tế:

- **Delays**: Random delays 10-100ms
- **Packet Loss**: 10% messages bị mất
- **Duplicates**: 5% messages bị duplicate
- **Reordering**: Messages đến không theo thứ tự

## Performance

Với cấu hình mặc định (4 validators):

- **Finalization Time**: ~300-500ms per block
- **Throughput**: ~10-50 tx/s
- **Fault Tolerance**: Tolerates 1 Byzantine validator
- **Network Overhead**: ~100-200 messages per block


## Tài liệu tham khảo

- **Tendermint Consensus**: https://tendermint.com/docs/
- **Ed25519**: https://ed25519.cr.yp.to/
- **Byzantine Fault Tolerance**: https://pmg.csail.mit.edu/papers/osdi99.pdf