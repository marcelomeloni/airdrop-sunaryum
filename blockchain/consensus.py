class ProofOfEnergy:
    def __init__(self, blockchain):
        self.blockchain = blockchain
        self.energy_tolerance = 0.05

    def validate_node(self, node_id, reported_energy):
        return True

    def mint_tokens(self, validated_energy):
        """20KW (20,000 Watts) = 1 token"""
        return validated_energy / 20.0  # Assume energia em KW