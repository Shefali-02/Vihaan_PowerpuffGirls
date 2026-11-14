// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title AnchorRegistry
/// @notice Stores Merkle roots of Munshi audit batches. Only hashes, a pseudonymous
///         workspace id and a batch sequence number are ever written here.
contract AnchorRegistry {
    address public immutable anchorer;

    /// workspace (sha256 pseudonym) => batch seq => Merkle root
    mapping(bytes32 => mapping(uint64 => bytes32)) public rootOf;

    event Anchored(bytes32 indexed workspace, uint64 indexed seq, bytes32 root, uint64 ts);

    error NotAnchorer();
    error AlreadyAnchored();
    error EmptyRoot();

    constructor(address _anchorer) {
        anchorer = _anchorer;
    }

    function anchor(bytes32 ws, uint64 seq, bytes32 root) external {
        if (msg.sender != anchorer) revert NotAnchorer();
        if (root == bytes32(0)) revert EmptyRoot();
        if (rootOf[ws][seq] != bytes32(0)) revert AlreadyAnchored();
        rootOf[ws][seq] = root;
        emit Anchored(ws, seq, root, uint64(block.timestamp));
    }
}
