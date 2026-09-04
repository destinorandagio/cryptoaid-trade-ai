// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @dev Minimal interface for ERC20 (USDT on Polygon has 6 decimals)
 */
interface IERC20 {
    function totalSupply() external view returns (uint256);
    function balanceOf(address account) external view returns (uint256);
    function transfer(address recipient, uint256 amount) external returns (bool);
    function allowance(address owner, address spender) external view returns (uint256);
    function approve(address spender, uint256 amount) external returns (bool);
    function transferFrom(address sender, address recipient, uint256 amount) external returns (bool);
}

/**
 * @title TradeAidPropFactory
 * @notice On-Chain Prop Challenge Factory & Credit Wallet for TradeAID AI Ecosystem on Polygon POS.
 * @dev Manages 3-Tier challenge purchases (POL/USDT), 80% real profit share payouts,
 * and Second Chance fee conversion to internal TradeAid Credits (TAC).
 *
 * Treasury Address: 0x3C320B3a0917fF44BF6551CDdee44402AFcF250C
 * Polygon POS Chain ID: 137
 * USDT on Polygon: 0xc2132D05D31c914a87C6611C10748AEb04B58e8F (6 Decimals)
 */
contract TradeAidPropFactory {

    // ====================================================================
    // CUSTOM ERRORS
    // ====================================================================
    error InvalidAddress();
    error InvalidTier();
    error InsufficientPayment(uint256 sent, uint256 required);
    error ChallengeNotActive();
    error ChallengeAlreadyResolved();
    error Unauthorized();
    error TransferFailed();
    error ContractPaused();
    error InsufficientContractBalance();
    error InsufficientCreditBalance();

    // ====================================================================
    // ENUMS & STRUCTS
    // ====================================================================
    enum Tier { STARTER, PRO, ELITE }
    enum ChallengeStatus { ACTIVE, PASSED, FAILED, PAYOUT_CLAIMED }

    struct TierConfig {
        uint256 feeUsdt;        // In 6 decimals (e.g. 50 * 1e6 for 50 USDT)
        uint256 feePol;         // In 18 decimals (e.g. 150 POL)
        uint256 virtualCapital; // Virtual capital ($50,000, $100,000, $150,000)
        uint16 leverage;        // 1000x for STARTER/PRO, 100x for ELITE
        uint16 profitTargetBps; // 800 bps = 8.00%
        uint16 maxTotalDdBps;   // 1000 bps = 10.00%
        uint16 payoutShareBps;  // 8000 bps = 80.00%
    }

    struct Challenge {
        uint256 id;
        address user;
        Tier tier;
        uint256 feePaid;
        address paymentToken;   // address(0) for native POL, USDT address for ERC20
        uint256 createdAt;
        ChallengeStatus status;
        uint256 payoutClaimed;  // Amount of USDT profit paid out
    }

    // ====================================================================
    // EVENTS
    // ====================================================================
    event ChallengeCreated(
        uint256 indexed challengeId,
        address indexed user,
        Tier indexed tier,
        uint256 feePaid,
        address paymentToken,
        uint256 virtualCapital,
        uint256 timestamp
    );

    event ChallengeResolved(
        uint256 indexed challengeId,
        address indexed user,
        ChallengeStatus status,
        uint256 tacCreditAwarded,
        uint256 timestamp
    );

    event PayoutClaimed(
        uint256 indexed challengeId,
        address indexed user,
        uint256 profitAmountUsdt,
        uint256 userShareUsdt, // 80% of profit
        uint256 timestamp
    );

    event CreditsUsed(
        address indexed user,
        uint256 amountTac,
        string reason,
        uint256 timestamp
    );

    event TreasuryUpdated(address indexed oldTreasury, address indexed newTreasury);
    event OracleUpdated(address indexed oldOracle, address indexed newOracle);
    event PausedStateChanged(bool isPaused);

    // ====================================================================
    // STORAGE
    // ====================================================================
    address public owner;
    address payable public treasury;
    address public cortexOracle;
    IERC20 public immutable usdtToken;
    bool public paused;

    uint256 public nextChallengeId = 1;

    // Mapping: Tier => Configuration
    mapping(Tier => TierConfig) public tiers;

    // Challenges registry: challengeId => Challenge
    mapping(uint256 => Challenge) public challenges;

    // User active challenges list: user => challengeIds[]
    mapping(address => uint256[]) public userChallenges;

    // Second Chance Wallet: user => TradeAid Credits (TAC) in 6 decimals ($1 credit = 1 USDT)
    mapping(address => uint256) public userCredits;

    // Total metrics
    uint256 public totalChallengesCreated;
    uint256 public totalFeesCollectedUsdt;
    uint256 public totalPayoutsDistributedUsdt;
    uint256 public totalTacCreditsAwarded;

    // ====================================================================
    // MODIFIERS
    // ====================================================================
    modifier onlyOwner() {
        if (msg.sender != owner) revert Unauthorized();
        _;
    }

    modifier onlyOracleOrOwner() {
        if (msg.sender != cortexOracle && msg.sender != owner) revert Unauthorized();
        _;
    }

    modifier whenNotPaused() {
        if (paused) revert ContractPaused();
        _;
    }

    // ====================================================================
    // CONSTRUCTOR
    // ====================================================================
    constructor(
        address payable _treasury,
        address _cortexOracle,
        address _usdtToken
    ) {
        if (_treasury == address(0) || _cortexOracle == address(0) || _usdtToken == address(0)) {
            revert InvalidAddress();
        }
        owner = msg.sender;
        treasury = _treasury;
        cortexOracle = _cortexOracle;
        usdtToken = IERC20(_usdtToken);

        // Configure standard 3 Tiers (USDT: 6 decimals, POL: 18 decimals)
        // 1. STARTER: $50 USDT, $50,000 Virtual, 1000x, 8% Target, -10% Max DD, 80% Payout
        tiers[Tier.STARTER] = TierConfig({
            feeUsdt: 50 * 1e6,
            feePol: 150 ether,          // ~50 USD at ~$0.33 POL
            virtualCapital: 50000 * 1e6,
            leverage: 1000,
            profitTargetBps: 800,       // 8.00%
            maxTotalDdBps: 1000,        // 10.00%
            payoutShareBps: 8000        // 80.00%
        });

        // 2. PRO: $100 USDT, $100,000 Virtual, 1000x, 8% Target, -10% Max DD, 80% Payout
        tiers[Tier.PRO] = TierConfig({
            feeUsdt: 100 * 1e6,
            feePol: 300 ether,          // ~100 USD at ~$0.33 POL
            virtualCapital: 100000 * 1e6,
            leverage: 1000,
            profitTargetBps: 800,
            maxTotalDdBps: 1000,
            payoutShareBps: 8000
        });

        // 3. ELITE: $1,500 USDT, $150,000 Virtual, 100x, 8% Target, -10% Max DD, 80% Payout
        tiers[Tier.ELITE] = TierConfig({
            feeUsdt: 1500 * 1e6,
            feePol: 4500 ether,         // ~1500 USD at ~$0.33 POL
            virtualCapital: 150000 * 1e6,
            leverage: 100,
            profitTargetBps: 800,
            maxTotalDdBps: 1000,
            payoutShareBps: 8000
        });
    }

    // ====================================================================
    // USER ACTIONS
    // ====================================================================

    /**
     * @notice Buy a Prop Challenge with USDT on Polygon
     * @param tier STARTER (0), PRO (1), or ELITE (2)
     */
    function buyChallengeWithUsdt(Tier tier) external whenNotPaused returns (uint256 challengeId) {
        TierConfig memory conf = tiers[tier];
        if (conf.feeUsdt == 0) revert InvalidTier();

        // Pull USDT fee from user to Treasury
        bool success = usdtToken.transferFrom(msg.sender, treasury, conf.feeUsdt);
        if (!success) revert TransferFailed();

        challengeId = _createChallenge(msg.sender, tier, conf.feeUsdt, address(usdtToken));
        totalFeesCollectedUsdt += conf.feeUsdt;
    }

    /**
     * @notice Buy a Prop Challenge with native POL on Polygon
     * @param tier STARTER (0), PRO (1), or ELITE (2)
     */
    function buyChallengeWithPol(Tier tier) external payable whenNotPaused returns (uint256 challengeId) {
        TierConfig memory conf = tiers[tier];
        if (conf.feePol == 0) revert InvalidTier();
        if (msg.value < conf.feePol) revert InsufficientPayment(msg.value, conf.feePol);

        // Forward native POL to Treasury
        (bool sent, ) = treasury.call{value: msg.value}("");
        if (!sent) revert TransferFailed();

        challengeId = _createChallenge(msg.sender, tier, msg.value, address(0));
    }

    /**
     * @notice Use accumulated TradeAid Credits (TAC) to buy or discount a Challenge
     * @param tier The desired Challenge Tier
     */
    function buyChallengeWithCredits(Tier tier) external whenNotPaused returns (uint256 challengeId) {
        TierConfig memory conf = tiers[tier];
        if (conf.feeUsdt == 0) revert InvalidTier();
        if (userCredits[msg.sender] < conf.feeUsdt) revert InsufficientCreditBalance();

        userCredits[msg.sender] -= conf.feeUsdt;

        emit CreditsUsed(msg.sender, conf.feeUsdt, "CHALLENGE_PURCHASE_WITH_TAC", block.timestamp);

        challengeId = _createChallenge(msg.sender, tier, conf.feeUsdt, address(this));
    }

    /**
     * @notice Claim 80% profit share in real USDT from verified trading gains
     * @param challengeId ID of the passed or funded challenge
     * @param grossProfitUsdt Total verified gross profit generated by TradeAID in virtual dollars (6 decimals)
     */
    function claimPayout(uint256 challengeId, uint256 grossProfitUsdt) external whenNotPaused {
        Challenge storage ch = challenges[challengeId];
        if (ch.user != msg.sender) revert Unauthorized();
        if (ch.status != ChallengeStatus.PASSED) revert ChallengeNotActive();

        TierConfig memory conf = tiers[ch.tier];
        uint256 userShareUsdt = (grossProfitUsdt * conf.payoutShareBps) / 10000; // 80%

        if (usdtToken.balanceOf(address(this)) < userShareUsdt) {
            revert InsufficientContractBalance();
        }

        ch.status = ChallengeStatus.PAYOUT_CLAIMED;
        ch.payoutClaimed += userShareUsdt;
        totalPayoutsDistributedUsdt += userShareUsdt;

        bool success = usdtToken.transfer(msg.sender, userShareUsdt);
        if (!success) revert TransferFailed();

        emit PayoutClaimed(challengeId, msg.sender, grossProfitUsdt, userShareUsdt, block.timestamp);
    }

    // ====================================================================
    // ORACLE / CORTEX GOVERNANCE (CHALLENGE EVALUATION & TAC RECOVERY)
    // ====================================================================

    /**
     * @notice CORTEX Oracle marks a challenge as FAILED (e.g. Drawdown breach).
     * Automatically converts 100% of the challenge fee into TradeAid Credits (TAC).
     * @param challengeId ID of the challenge
     */
    function resolveFailedChallenge(uint256 challengeId) external onlyOracleOrOwner {
        Challenge storage ch = challenges[challengeId];
        if (ch.status != ChallengeStatus.ACTIVE) revert ChallengeAlreadyResolved();

        ch.status = ChallengeStatus.FAILED;

        // Second Chance Recovery: Convert 100% fee to TradeAid Credits (TAC)
        TierConfig memory conf = tiers[ch.tier];
        uint256 creditAwarded = conf.feeUsdt; // 1 TAC = 1 USDT (6 decimals)
        userCredits[ch.user] += creditAwarded;
        totalTacCreditsAwarded += creditAwarded;

        emit ChallengeResolved(challengeId, ch.user, ChallengeStatus.FAILED, creditAwarded, block.timestamp);
    }

    /**
     * @notice CORTEX Oracle marks a challenge as PASSED (+8% profit target met without breaches)
     * @param challengeId ID of the challenge
     */
    function resolvePassedChallenge(uint256 challengeId) external onlyOracleOrOwner {
        Challenge storage ch = challenges[challengeId];
        if (ch.status != ChallengeStatus.ACTIVE) revert ChallengeAlreadyResolved();

        ch.status = ChallengeStatus.PASSED;

        emit ChallengeResolved(challengeId, ch.user, ChallengeStatus.PASSED, 0, block.timestamp);
    }

    // ====================================================================
    // INTERNAL HELPERS
    // ====================================================================
    function _createChallenge(
        address user,
        Tier tier,
        uint256 feePaid,
        address paymentToken
    ) internal returns (uint256 challengeId) {
        challengeId = nextChallengeId++;
        TierConfig memory conf = tiers[tier];

        challenges[challengeId] = Challenge({
            id: challengeId,
            user: user,
            tier: tier,
            feePaid: feePaid,
            paymentToken: paymentToken,
            createdAt: block.timestamp,
            status: ChallengeStatus.ACTIVE,
            payoutClaimed: 0
        });

        userChallenges[user].push(challengeId);
        totalChallengesCreated++;

        emit ChallengeCreated(
            challengeId,
            user,
            tier,
            feePaid,
            paymentToken,
            conf.virtualCapital,
            block.timestamp
        );
    }

    // ====================================================================
    // ADMIN FUNCTIONS
    // ====================================================================
    function setTreasury(address payable _newTreasury) external onlyOwner {
        if (_newTreasury == address(0)) revert InvalidAddress();
        emit TreasuryUpdated(treasury, _newTreasury);
        treasury = _newTreasury;
    }

    function setCortexOracle(address _newOracle) external onlyOwner {
        if (_newOracle == address(0)) revert InvalidAddress();
        emit OracleUpdated(cortexOracle, _newOracle);
        cortexOracle = _newOracle;
    }

    function setPaused(bool _paused) external onlyOwner {
        paused = _paused;
        emit PausedStateChanged(_paused);
    }

    function updateTier(
        Tier tier,
        uint256 feeUsdt,
        uint256 feePol,
        uint256 virtualCapital,
        uint16 leverage,
        uint16 profitTargetBps,
        uint16 maxTotalDdBps,
        uint16 payoutShareBps
    ) external onlyOwner {
        tiers[tier] = TierConfig({
            feeUsdt: feeUsdt,
            feePol: feePol,
            virtualCapital: virtualCapital,
            leverage: leverage,
            profitTargetBps: profitTargetBps,
            maxTotalDdBps: maxTotalDdBps,
            payoutShareBps: payoutShareBps
        });
    }

    /**
     * @notice Deposit funds to the Payout Pool (in USDT)
     */
    function fundPayoutPool(uint256 amountUsdt) external {
        bool success = usdtToken.transferFrom(msg.sender, address(this), amountUsdt);
        if (!success) revert TransferFailed();
    }

    // ====================================================================
    // VIEW FUNCTIONS
    // ====================================================================
    function getUserChallenges(address user) external view returns (uint256[] memory) {
        return userChallenges[user];
    }

    function getTierInfo(Tier tier) external view returns (TierConfig memory) {
        return tiers[tier];
    }

    receive() external payable {
        // Accept direct POL deposits to treasury
        (bool sent, ) = treasury.call{value: msg.value}("");
        if (!sent) revert TransferFailed();
    }
}
