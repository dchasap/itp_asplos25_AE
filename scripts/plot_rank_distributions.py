import csv
import matplotlib.pyplot as plt
from collections import defaultdict
import sys

# Usage: python plot_rank_distributions.py <csv_file>

def load_rank_distributions(csv_file):
    set_ranks = defaultdict(lambda: defaultdict(int))
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            set_id = int(row['set_id'])
            rank = int(row['rank'])
            count = int(row['count'])
            set_ranks[set_id][rank] = count
    return set_ranks

def plot_distributions(set_ranks, max_sets=8, k=16):
    # Plot all sets
    plt.figure(figsize=(14, 8))
    all_probs = []
    for set_id, rank_counts in sorted(set_ranks.items()):
        ranks = list(range(k))
        counts = [rank_counts.get(r, 0) for r in ranks]
        total = sum(counts)
        if total > 0:
            probs = [100.0 * c / total for c in counts]
        else:
            probs = [0 for _ in counts]
        all_probs.append(probs)
        plt.plot(ranks, probs, alpha=0.3, color='gray')
    plt.xlabel('Rank')
    plt.ylabel('Probability (%)')
    plt.title('Rank Probability Distributions (Percent) for All Sets')
    plt.grid(True)
    plt.tight_layout()
    #plt.show()
    plt.savefig("./figures/ranks_dist1.png", dpi=170)

    # Summary figure: mean and stddev across sets for each rank
    import numpy as np
    all_probs_np = np.array(all_probs)
    mean_probs = np.mean(all_probs_np, axis=0)
    std_probs = np.std(all_probs_np, axis=0)
    plt.figure(figsize=(14, 8))
    plt.plot(ranks, mean_probs, marker='o', label='Mean Probability')
    plt.fill_between(ranks, mean_probs-std_probs, mean_probs+std_probs, color='blue', alpha=0.2, label='Std Dev')
    plt.xlabel('Rank')
    plt.ylabel('Probability (%)')
    plt.title('Mean ± Std Dev of Rank Probability Across All Sets')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    #plt.show()
    plt.savefig("./figures/ranks_dist2.png", dpi=170)

def main():
    if len(sys.argv) < 2:
        print("Usage: python plot_rank_distributions.py <csv_file>")
        sys.exit(1)
    csv_file = sys.argv[1]
    set_ranks = load_rank_distributions(csv_file)
    plot_distributions(set_ranks)

if __name__ == "__main__":
    main()
