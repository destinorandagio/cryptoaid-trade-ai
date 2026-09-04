// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title TradeAidActivator
 * @notice On-Chain Activation & Viral Referral Engine for CryptoAID Trade AI on Polygon POS.
 * @dev Manages the 10 POL Activation Fee, 2 POL viral referral payout, and treasury settlement.
 * 
 * Treasury Default: 0x3C320B3a0917fF44BF6551CDdee44402AFcF250C
 * Polygon POS Chain ID: 137 (Native currency: POL)
 */
contract TradeAidActivator {

    // ====================================================================
    // CUSTOM ERRORS (Gas-Efficient)
    // ====================================================================
    error InvalidAddress();
    error InsufficientActivationFee(uint256 sent, uint256 required);
    error AlreadyActivated();
    error ReferralSelfNotAllowed();
    error TransferFailed();
    error ContractPaused();
    error NotOwner();

    // ====================================================================
    // EVENTS
    // ====================================================================
    event ActivationConfirmed(
        address indexed user,
        address indexed referrer,
        uint256 amountPaid,
        uint256 referralReward,
        uint256 indexed timestamp
    );
    event ReferralPaid(
        address indexed referrer,
        address indexed referee,
        uint256 rewardAmount,
        uint256 timestamp
    );
    event TreasuryUpdated(address indexed oldTreasury, address indexed newTreasury);
    event FeesUpdated(uint256 newActivationFee, uint256 newReferralReward);
    event PausedStateChanged(bool isPaused);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    // ====================================================================
    // STORAGE
    // ====================================================================
    address public owner;
    address payable public treasury;
    bool public paused;

    // Fees (18 decimals for POL on Polygon)
    uint256 public activationFee = 10 ether;   // 10 POL
    uint256 public referralReward = 2 ether;   // 2 POL reward to referrer

    // User State
    mapping(address => bool) public isActivated;
    mapping(address => uint256) public activatedAt;
    mapping(address => address) public userReferrer;
    mapping(address => uint256) public referralCount;
    mapping(address => uint256) public totalReferralEarnings;

    // Protocol Metrics
    uint256 public totalActivatedUsers;
    uint256 public totalPOLCollected;
    uint256 public totalReferralRewardsPaid;

    // Reentrancy guard
    uint256 private _status;
    uint256 private constant _NOT_ENTERED = 1;
    uint256 private constant _ENTERED = 2;

    // ====================================================================
    // MODIFIERS
    // ====================================================================
    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    modifier whenNotPaused() {
        if (paused) revert ContractPaused();
        _;
    }

    modifier nonReentrant() {
        if (_status == _ENTERED) revert TransferFailed();
        _status = _ENTERED;
        _;
        _status = _NOT_ENTERED;
    }

    // ====================================================================
    // CONSTRUCTOR
    // ====================================================================
    constructor(address payable _treasury) {
        if (_treasury == address(0)) revert InvalidAddress();
        owner = msg.sender;
        treasury = _treasury;
        _status = _NOT_ENTERED;
        emit OwnershipTransferred(address(0), msg.sender);
        emit TreasuryUpdated(address(0), _treasury);
    }

    // ====================================================================
    // CORE ACTIVATION FUNCTION
    // ====================================================================

    /**
     * @notice Activates user's TradeAID Autotrade access with 10 POL and handles viral referral.
     * @param referrer Address of the referrer (address(0) if none).
     */
    function activateSubscription(address referrer) 
        external 
        payable 
        whenNotPaused 
        nonReentrant 
    {
        if (msg.value < activationFee) {
            revert InsufficientActivationFee(msg.value, activationFee);
        }
        if (isActivated[msg.sender]) {
            revert AlreadyActivated();
        }
        if (referrer == msg.sender) {
            revert ReferralSelfNotAllowed();
        }

        isActivated[msg.sender] = true;
        activatedAt[msg.sender] = block.timestamp;
        totalActivatedUsers += 1;
        totalPOLCollected += activationFee;

        uint256 rewardPaid = 0;
        address validReferrer = address(0);

        // Check if referrer is valid (active trader and non-zero)
        if (referrer != address(0) && isActivated[referrer]) {
            validReferrer = referrer;
            userReferrer[msg.sender] = referrer;
            referralCount[referrer] += 1;
            totalReferralEarnings[referrer] += referralReward;
            totalReferralRewardsPaid += referralReward;
            rewardPaid = referralReward;

            // Pay 2 POL immediately to referrer
            (bool refSuccess, ) = payable(referrer).call{value: referralReward}("");
            if (!refSuccess) revert TransferFailed();

            emit ReferralPaid(referrer, msg.sender, referralReward, block.timestamp);
        }

        // Pay remainder to Treasury (8 POL if referral paid, otherwise full 10 POL)
        uint256 treasuryAmount = activationFee - rewardPaid;
        (bool treasurySuccess, ) = treasury.call{value: treasuryAmount}("");
        if (!treasurySuccess) revert TransferFailed();

        // Refund any excess POL sent above activationFee
        if (msg.value > activationFee) {
            uint256 refund = msg.value - activationFee;
            (bool refundSuccess, ) = payable(msg.sender).call{value: refund}("");
            if (!refundSuccess) revert TransferFailed();
        }

        emit ActivationConfirmed(
            msg.sender,
            validReferrer,
            activationFee,
            rewardPaid,
            block.timestamp
        );
    }

    // ====================================================================
    // VIEW FUNCTIONS
    // ====================================================================

    /**
     * @notice Returns complete activation and referral status for an address.
     */
    function getUserStatus(address user) 
        external 
        view 
        returns (
            bool active,
            uint256 activationTimestamp,
            address referrer,
            uint256 totalReferrals,
            uint256 referralEarnings
        ) 
    {
        return (
            isActivated[user],
            activatedAt[user],
            userReferrer[user],
            referralCount[user],
            totalReferralEarnings[user]
        );
    }

    /**
     * @notice Returns protocol-level activation and revenue metrics.
     */
    function getProtocolMetrics() 
        external 
        view 
        returns (
            uint256 users,
            uint256 polCollected,
            uint256 rewardsDistributed,
            uint256 currentFee,
            uint256 currentReferralReward
        ) 
    {
        return (
            totalActivatedUsers,
            totalPOLCollected,
            totalReferralRewardsPaid,
            activationFee,
            referralReward
        );
    }

    // ====================================================================
    // ADMIN FUNCTIONS
    // ====================================================================

    function setTreasury(address payable _newTreasury) external onlyOwner {
        if (_newTreasury == address(0)) revert InvalidAddress();
        address old = treasury;
        treasury = _newTreasury;
        emit TreasuryUpdated(old, _newTreasury);
    }

    function setFees(uint256 _newActivationFee, uint256 _newReferralReward) external onlyOwner {
        if (_newReferralReward > _newActivationFee) revert InvalidAddress();
        activationFee = _newActivationFee;
        referralReward = _newReferralReward;
        emit FeesUpdated(_newActivationFee, _newReferralReward);
    }

    function setPaused(bool _paused) external onlyOwner {
        paused = _paused;
        emit PausedStateChanged(_paused);
    }

    function transferOwnership(address newOwner) external onlyOwner {
        if (newOwner == address(0)) revert InvalidAddress();
        address old = owner;
        owner = newOwner;
        emit OwnershipTransferred(old, newOwner);
    }

    /**
     * @notice Emergency withdrawal in case funds get locked.
     */
    function emergencyWithdraw() external onlyOwner {
        uint256 balance = address(this).balance;
        if (balance > 0) {
            (bool ok, ) = treasury.call{value: balance}("");
            if (!ok) revert TransferFailed();
        }
    }

    // Reject raw POL deposits without function call
    receive() external payable {
        revert("Direct deposits not accepted. Call activateSubscription()");
    }
}
