import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors

class Recommender:
    def __init__(self, n_neighbors=10):
        self.scaler = StandardScaler()
        self.model = NearestNeighbors(n_neighbors=n_neighbors)

    def train(self, df):
        numeric_df = df.select_dtypes(include='number').dropna(axis=1, how='all').dropna()
        scaled = self.scaler.fit_transform(numeric_df)
        self.model.fit(scaled)
        return numeric_df

    def recommend(self, seed_df, candidate_df):
        seed_scaled = self.scaler.transform(seed_df)
        candidate_scaled = self.scaler.transform(candidate_df)

        distances, indices = self.model.kneighbors(seed_scaled)

        flat_indices = []
        seen = set()
        for neighbor_list in indices:
            for idx in neighbor_list:
                if idx not in seen:
                    flat_indices.append(idx)
                    seen.add(idx)

        return flat_indices
