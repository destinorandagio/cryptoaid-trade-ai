// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title TradeAidRunRewardPool
 * @notice Dedicated Smart Contract for LEDGER 1: AUTOTRADE RUN DEMO GAMIFICATA
 *
 * ECONOMIC CONTRACT:
 * 1. User pays 10 POL Access Fee to B+ DAO Treasury (`0x3C320B3a0917fF44BF6551CDdee44402AFcF250C`).
 * 2. Autotrade Run runs on 10,000 USDT PAPER Capital for maximum 180s.
 * 3. A separate RewardPool holds protocol funds.
 * 4. WIN Condition: Net P&L > 0.00% & 0 CORTEX violations within run window.
 * 5. If WIN and RewardPool is solvent (>= 2 POL), user receives 2 POL reward.
 * 6. If LOSS, user receives 0 POL.
 *
 * Solvency Rule: Rewards are paid ONLY if the contract pool is funded.
 */
contract TradeAidRunRewardPool {
    address public immutable daoTreasury;
    address public oracleOperator;
    address public owner;

    uint256 public constant RUN_FEE_POL = 10 ether; // 10 POL
    uint256 public constant RUN_REWARD_POL = 2 ether; // 2 POL reward for verified WIN

    // Running counter
    uint256 public nextRunSequence = 100;
    uint256 public totalRunsActivated = 0;
    uint256 public totalRewardsClaimed = 0;

    enum RunStatus { NONE, RUNNING, WON, LOST, REWARD_CLAIMED }

    struct AutotradeRun {
        uint256 sequenceId;
        address user;
        uint256 startTime;
        uint256 maxDuration; // in seconds (e.g. 180s)
        RunStatus status;
        bool rewardPaid;
    }

    // runId => AutotradeRun
    mapping(bytes32 => AutotradeRun) public runs;

    event RewardPoolFunded(address indexed sender, uint256 amountPol, uint256 newPoolBalance);
    event AutotradeRunStarted(bytes32 indexed runId, uint256 sequenceId, address indexed user, uint256 feePaid);
    event AutotradeRunResolved(bytes32 indexed runId, address indexed user, bool won, int256 pnlBps);
    event RewardClaimed(bytes32 indexed runId, address indexed winner, uint256 rewardAmount);
    event OperatorUpdated(address indexed previousOperator, address indexed newOperator);

    modifier onlyOperator() {
        require(msg.sender == oracleOperator || msg.sender == owner, "Unauthorized operator");
        _;
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner");
        _;
    }

    constructor(address _daoTreasury, address _oracleOperator) {
        require(_daoTreasury != address(0), "Invalid DAO treasury");
        require(_oracleOperator != address(0), "Invalid operator");
        owner = msg.sender;
        daoTreasury = _daoTreasury;
        oracleOperator = _oracleOperator;
    }

    /**
     * @notice Funds the Reward Pool with POL
     */
    function fundRewardPool() external payable {
        require(msg.value > 0, "Zero deposit");
        emit RewardPoolFunded(msg.sender, msg.value, address(this).balance);
    }

    /**
     * @notice Fallback to accept direct POL donations to the Reward Pool
     */
    receive() external payable {
        emit RewardPoolFunded(msg.sender, msg.value, address(this).balance);
    }

    /**
     * @notice User starts a gamified Autotrade Run by paying 10 POL fee
     * The 10 POL fee is immediately forwarded to the DAO Treasury
     */
    function startAutotradeRun() external payable returns (bytes32 runId, uint256 sequenceId) {
        require(msg.value == RUN_FEE_POL, "Exact 10 POL fee required");

        // Forward fee to DAO Treasury
        (bool feeSent, ) = payable(daoTreasury).call{value: msg.value}("");
        require(feeSent, "Failed forwarding fee to DAO Treasury");

        sequenceId = ++nextRunSequence;
        runId = keccak256(abi.encodePacked(block.chainid, msg.sender, sequenceId, block.timestamp));

        runs[runId] = AutotradeRun({
            sequenceId: sequenceId,
            user: msg.sender,
            startTime: block.timestamp,
            maxDuration: 180, // 3 minutes max duration
            status: RunStatus.RUNNING,
            rewardPaid: false
        });

        totalRunsActivated++;

        emit AutotradeRunStarted(runId, sequenceId, msg.sender, msg.value);
        return (runId, sequenceId);
    }

    /**
     * @notice Oracle resolves run result and dispatches 2 POL reward if WIN and pool is solvent
     * @param runId Unique identifier of the run
     * @param won True if net P&L > 0.00% and 0 CORTEX violations within duration
     * @param pnlBps Realized net P&L in basis points
     */
    function resolveAndClaimReward(bytes32 runId, bool won, int256 pnlBps) external onlyOperator {
        AutotradeRun storage r = runs[runId];
        require(r.user != address(0), "Run does not exist");
        require(r.status == RunStatus.RUNNING, "Run already closed");

        if (won) {
            r.status = RunStatus.WON;
            emit AutotradeRunResolved(runId, r.user, true, pnlBps);

            // Check RewardPool solvency
            if (address(this).balance >= RUN_REWARD_POL) {
                r.rewardPaid = true;
                r.status = RunStatus.REWARD_CLAIMED;
                totalRewardsClaimed += RUN_REWARD_POL;

                (bool sent, ) = payable(r.user).call{value: RUN_REWARD_POL}("");
                require(sent, "Reward transfer failed");

                emit RewardClaimed(runId, r.user, RUN_REWARD_POL);
            }
        } else {
            r.status = RunStatus.LOST;
            emit AutotradeRunResolved(runId, r.user, false, pnlBps);
        }
    }

    /**
     * @notice Returns current RewardPool balance and capacity (number of 2 POL payouts backed)
     */
    function getPoolStatus() external view returns (uint256 balanceWei, uint256 backedPayouts, bool isSolvent) {
        balanceWei = address(this).balance;
        backedPayouts = balanceWei / RUN_REWARD_POL;
        isSolvent = balanceWei >= RUN_REWARD_POL;
    }

    function setOracleOperator(address _newOperator) external onlyOwner {
        require(_newOperator != address(0), "Zero address");
        emit OperatorUpdated(oracleOperator, _newOperator);
        oracleOperator = _newOperator;
    }
}
