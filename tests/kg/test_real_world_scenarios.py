"""
Real-world scenario tests for KG algorithms.

Tests algorithms with realistic use cases and data patterns.
"""

import pytest
import networkx as nx
import numpy as np
from typing import Dict, List, Any, Tuple
import json
import time

from semantica.kg import (
    GraphBuilderWithProvenance,
    AlgorithmTrackerWithProvenance,
    NodeEmbedder,
    SimilarityCalculator,
    PathFinder,
    LinkPredictor,
    CentralityCalculator,
    CommunityDetector,
    ConnectivityAnalyzer
)


class TestRealWorldScenarios:
    """Test KG algorithms with real-world scenarios."""
    
    @pytest.fixture
    def academic_citation_network(self):
        """Create a realistic academic citation network."""
        graph = nx.DiGraph()
        
        # Papers with metadata
        papers = [
            ('P1', {
                'title': 'Deep Learning for Natural Language Processing',
                'authors': ['Alice Smith', 'Bob Johnson'],
                'year': 2020,
                'venue': 'ACL',
                'citations': 25,
                'field': 'NLP',
                'keywords': ['deep learning', 'nlp', 'transformers']
            }),
            ('P2', {
                'title': 'Attention Is All You Need',
                'authors': ['Charlie Brown', 'Diana Lee'],
                'year': 2017,
                'venue': 'NeurIPS',
                'citations': 15000,
                'field': 'NLP',
                'keywords': ['attention', 'transformers', 'nlp']
            }),
            ('P3', {
                'title': 'BERT: Pre-training of Deep Bidirectional Transformers',
                'authors': ['Eve Wilson', 'Frank Chen'],
                'year': 2018,
                'venue': 'ACL',
                'citations': 12000,
                'field': 'NLP',
                'keywords': ['bert', 'transformers', 'pre-training']
            }),
            ('P4', {
                'title': 'Graph Neural Networks for Social Network Analysis',
                'authors': ['Grace Kim', 'Henry Liu'],
                'year': 2021,
                'venue': 'WWW',
                'citations': 45,
                'field': 'Graph ML',
                'keywords': ['gcn', 'social networks', 'graph neural networks']
            }),
            ('P5', {
                'title': 'Node2Vec: Scalable Feature Learning for Networks',
                'authors': ['Iris Zhang', 'Jack Wang'],
                'year': 2018,
                'venue': 'KDD',
                'citations': 3000,
                'field': 'Graph ML',
                'keywords': ['node2vec', 'graph embeddings', 'network analysis']
            }),
            ('P6', {
                'title': 'Graph Attention Networks',
                'authors': ['Alice Smith', 'Kevin Park'],
                'year': 2018,
                'venue': 'ICLR',
                'citations': 5000,
                'field': 'Graph ML',
                'keywords': ['gat', 'attention', 'graph neural networks']
            }),
            ('P7', {
                'title': 'Convolutional Neural Networks for Image Classification',
                'authors': ['Laura Martinez', 'Mike Davis'],
                'year': 2019,
                'venue': 'CVPR',
                'citations': 800,
                'field': 'Computer Vision',
                'keywords': ['cnn', 'image classification', 'deep learning']
            }),
            ('P8', {
                'title': 'ResNet: Deep Residual Learning for Image Recognition',
                'authors': ['Nancy White', 'Tom Harris'],
                'year': 2016,
                'venue': 'CVPR',
                'citations': 100000,
                'field': 'Computer Vision',
                'keywords': ['resnet', 'residual learning', 'image recognition']
            })
        ]
        
        graph.add_nodes_from(papers)
        
        # Citations (edges)
        citations = [
            ('P1', 'P2', {'weight': 0.8, 'year': 2020}),
            ('P1', 'P3', {'weight': 0.9, 'year': 2020}),
            ('P2', 'P3', {'weight': 0.7, 'year': 2017}),
            ('P2', 'P6', {'weight': 0.8, 'year': 2017}),
            ('P3', 'P6', {'weight': 0.6, 'year': 2018}),
            ('P4', 'P5', {'weight': 0.7, 'year': 2021}),
            ('P4', 'P6', {'weight': 0.5, 'year': 2021}),
            ('P5', 'P6', {'weight': 0.8, 'year': 2018}),
            ('P6', 'P4', {'weight': 0.4, 'year': 2018}),
            ('P7', 'P8', {'weight': 0.6, 'year': 2019}),
            ('P8', 'P7', {'weight': 0.3, 'year': 2016})
        ]
        
        graph.add_edges_from(citations)
        return graph
    
    @pytest.fixture
    def social_media_network(self):
        """Create a realistic social media network."""
        graph = nx.Graph()
        
        # Users with metadata
        users = [
            ('U1', {
                'username': 'alice_tech',
                'name': 'Alice Thompson',
                'age': 28,
                'city': 'San Francisco',
                'interests': ['AI', 'Machine Learning', 'Python'],
                'followers': 1250,
                'following': 890,
                'posts': 342,
                'verified': True
            }),
            ('U2', {
                'username': 'bob_data',
                'name': 'Bob Chen',
                'age': 32,
                'city': 'New York',
                'interests': ['Data Science', 'R', 'Statistics'],
                'followers': 890,
                'following': 1200,
                'posts': 256,
                'verified': False
            }),
            ('U3', {
                'username': 'charlie_ai',
                'name': 'Charlie Rodriguez',
                'age': 25,
                'city': 'Seattle',
                'interests': ['Deep Learning', 'TensorFlow', 'PyTorch'],
                'followers': 2100,
                'following': 450,
                'posts': 189,
                'verified': True
            }),
            ('U4', {
                'username': 'diana_ml',
                'name': 'Diana Kumar',
                'age': 30,
                'city': 'Boston',
                'interests': ['Machine Learning', 'Research', 'Academia'],
                'followers': 567,
                'following': 234,
                'posts': 78,
                'verified': False
            }),
            ('U5', {
                'username': 'eve_dev',
                'name': 'Eve Johnson',
                'age': 27,
                'city': 'Austin',
                'interests': ['Web Development', 'JavaScript', 'React'],
                'followers': 1450,
                'following': 678,
                'posts': 423,
                'verified': False
            }),
            ('U6', {
                'username': 'frank_security',
                'name': 'Frank Wilson',
                'age': 35,
                'city': 'Washington DC',
                'interests': ['Cybersecurity', 'Network Security', 'Ethical Hacking'],
                'followers': 3400,
                'following': 123,
                'posts': 156,
                'verified': True
            }),
            ('U7', {
                'username': 'grace_design',
                'name': 'Grace Martinez',
                'age': 29,
                'city': 'Los Angeles',
                'interests': ['UI/UX Design', 'Product Design', 'Figma'],
                'followers': 2800,
                'following': 567,
                'posts': 234,
                'verified': True
            }),
            ('U8', {
                'username': 'henry_startup',
                'name': 'Henry Lee',
                'age': 31,
                'city': 'San Francisco',
                'interests': ['Startups', 'Entrepreneurship', 'Venture Capital'],
                'followers': 980,
                'following': 1450,
                'posts': 167,
                'verified': False
            }),
            ('U9', {
                'username': 'iris_research',
                'name': 'Iris Wang',
                'age': 26,
                'city': 'Cambridge',
                'interests': ['Research', 'Biology', 'Bioinformatics'],
                'followers': 450,
                'following': 890,
                'posts': 89,
                'verified': False
            }),
            ('U10', {
                'username': 'jack_finance',
                'name': 'Jack Brown',
                'age': 33,
                'city': 'New York',
                'interests': ['Finance', 'Investment', 'Cryptocurrency'],
                'followers': 3200,
                'following': 234,
                'posts': 445,
                'verified': True
            })
        ]
        
        graph.add_nodes_from(users)
        
        # Friendships (edges)
        friendships = [
            ('U1', 'U2', {'weight': 0.8, 'type': 'friend', 'duration_months': 24}),
            ('U1', 'U3', {'weight': 0.9, 'type': 'friend', 'duration_months': 18}),
            ('U1', 'U8', {'weight': 0.7, 'type': 'friend', 'duration_months': 12}),
            ('U2', 'U10', {'weight': 0.6, 'type': 'friend', 'duration_months': 36}),
            ('U3', 'U4', {'weight': 0.5, 'type': 'colleague', 'duration_months': 6}),
            ('U4', 'U9', {'weight': 0.4, 'type': 'colleague', 'duration_months': 8}),
            ('U5', 'U7', {'weight': 0.8, 'type': 'friend', 'duration_months': 15}),
            ('U6', 'U10', {'weight': 0.3, 'type': 'professional', 'duration_months': 9}),
            ('U7', 'U5', {'weight': 0.9, 'type': 'friend', 'duration_months': 20}),
            ('U8', 'U1', {'weight': 0.7, 'type': 'friend', 'duration_months': 12}),
            ('U9', 'U4', {'weight': 0.6, 'type': 'colleague', 'duration_months': 10}),
            ('U10', 'U2', {'weight': 0.8, 'type': 'friend', 'duration_months': 30})
        ]
        
        graph.add_edges_from(friendships)
        return graph
    
    @pytest.fixture
    def supply_chain_network(self):
        """Create a realistic supply chain network."""
        graph = nx.DiGraph()
        
        # Supply chain entities
        entities = [
            ('SUP1', {
                'type': 'Supplier',
                'name': 'Global Electronics Inc',
                'location': 'Shenzhen, China',
                'products': ['Semiconductors', 'PCBs'],
                'capacity': 1000000,
                'quality_score': 0.95
            }),
            ('SUP2', {
                'type': 'Supplier',
                'name': 'Precision Components Ltd',
                'location': 'Taipei, Taiwan',
                'products': ['Connectors', 'Cables'],
                'capacity': 500000,
                'quality_score': 0.92
            }),
            ('MAN1', {
                'type': 'Manufacturer',
                'name': 'Tech Manufacturing Co',
                'location': 'Austin, Texas',
                'products': ['Smartphones', 'Tablets'],
                'capacity': 200000,
                'quality_score': 0.98
            }),
            ('MAN2', {
                'type': 'Manufacturer',
                'name': 'Device Assembly Inc',
                'location': 'Phoenix, Arizona',
                'products': ['Laptops', 'Monitors'],
                'capacity': 150000,
                'quality_score': 0.94
            }),
            ('DIST1', {
                'type': 'Distributor',
                'name': 'National Distribution Corp',
                'location': 'Chicago, Illinois',
                'coverage': 'Nationwide',
                'capacity': 500000,
                'quality_score': 0.96
            }),
            ('DIST2', {
                'type': 'Distributor',
                'name': 'Regional Logistics LLC',
                'location': 'Atlanta, Georgia',
                'coverage': 'Southeast',
                'capacity': 300000,
                'quality_score': 0.93
            }),
            ('RET1', {
                'type': 'Retailer',
                'name': 'TechMart Superstores',
                'location': 'New York, NY',
                'stores': 150,
                'revenue': 50000000,
                'quality_score': 0.97
            }),
            ('RET2', {
                'type': 'Retailer',
                'name': 'Electronics Plus',
                'location': 'Los Angeles, CA',
                'stores': 75,
                'revenue': 25000000,
                'quality_score': 0.91
            }),
            ('RET3', {
                'type': 'Retailer',
                'name': 'Online Tech Store',
                'location': 'Seattle, WA',
                'stores': 1,  # Online only
                'revenue': 75000000,
                'quality_score': 0.95
            })
        ]
        
        graph.add_nodes_from(entities)
        
        # Supply chain relationships
        relationships = [
            ('SUP1', 'MAN1', {'weight': 0.8, 'product': 'Semiconductors', 'lead_time_days': 30}),
            ('SUP1', 'MAN2', {'weight': 0.6, 'product': 'PCBs', 'lead_time_days': 45}),
            ('SUP2', 'MAN1', {'weight': 0.7, 'product': 'Connectors', 'lead_time_days': 25}),
            ('SUP2', 'MAN2', {'weight': 0.5, 'product': 'Cables', 'lead_time_days': 35}),
            ('MAN1', 'DIST1', {'weight': 0.9, 'product': 'Smartphones', 'lead_time_days': 15}),
            ('MAN1', 'DIST2', {'weight': 0.7, 'product': 'Tablets', 'lead_time_days': 20}),
            ('MAN2', 'DIST1', {'weight': 0.8, 'product': 'Laptops', 'lead_time_days': 18}),
            ('MAN2', 'DIST2', {'weight': 0.6, 'product': 'Monitors', 'lead_time_days': 22}),
            ('DIST1', 'RET1', {'weight': 0.9, 'product': 'Electronics', 'lead_time_days': 7}),
            ('DIST1', 'RET2', {'weight': 0.7, 'product': 'Electronics', 'lead_time_days': 10}),
            ('DIST1', 'RET3', {'weight': 0.8, 'product': 'Electronics', 'lead_time_days': 5}),
            ('DIST2', 'RET2', {'weight': 0.8, 'product': 'Electronics', 'lead_time_days': 8}),
            ('DIST2', 'RET3', {'weight': 0.6, 'product': 'Electronics', 'lead_time_days': 12})
        ]
        
        graph.add_edges_from(relationships)
        return graph
    
    @pytest.fixture
    def academic_embeddings(self):
        """Generate realistic academic paper embeddings."""
        np.random.seed(42)
        
        # Create embeddings based on field similarity
        field_embeddings = {
            'NLP': np.array([0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]),
            'Graph ML': np.array([0.4, 0.5, 0.6, 0.7, 0.8, 0.7, 0.6, 0.5]),
            'Computer Vision': np.array([0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9])
        }
        
        papers = ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8']
        fields = ['NLP', 'NLP', 'NLP', 'Graph ML', 'Graph ML', 'Graph ML', 'Computer Vision', 'Computer Vision']
        
        embeddings = {}
        for i, (paper, field) in enumerate(zip(papers, fields)):
            # Base embedding from field
            base_embedding = field_embeddings[field]
            
            # Add some noise and paper-specific variation
            noise = np.random.randn(8) * 0.1
            paper_embedding = base_embedding + noise
            
            # Normalize
            paper_embedding = paper_embedding / np.linalg.norm(paper_embedding)
            embeddings[paper] = paper_embedding.tolist()
        
        return embeddings
    
    def test_academic_citation_analysis(self, academic_citation_network, academic_embeddings):
        """Test academic citation network analysis."""
        # Initialize algorithms
        centrality_calc = CentralityCalculator()
        path_finder = PathFinder()
        link_predictor = LinkPredictor()
        sim_calc = SimilarityCalculator()
        tracker = AlgorithmTrackerWithProvenance(provenance=True)
        
        # Convert to dict format
        graph_dict = {
            'nodes': list(academic_citation_network.nodes()),
            'edges': list(academic_citation_network.edges())
        }
        
        # 1. Calculate PageRank (academic influence)
        pagerank_result = centrality_calc.calculate_pagerank(
            graph=academic_citation_network,
            alpha=0.85,
            max_iter=100
        )
        
        assert 'centrality' in pagerank_result
        assert 'rankings' in pagerank_result
        
        # Track with provenance
        pr_id = tracker.track_centrality_calculation(
            graph=academic_citation_network,
            centrality_scores=pagerank_result['centrality'],
            method='pagerank',
            parameters={'alpha': 0.85, 'max_iter': 100},
            source='academic_analysis'
        )
        
        # 2. Find citation paths
        try:
            citation_paths = path_finder.all_shortest_paths(academic_citation_network, 'P2')
            assert isinstance(citation_paths, dict)
            
            # Track path analysis
            path_id = tracker.track_path_analysis(
                graph=academic_citation_network,
                source='P2',
                paths=citation_paths,
                method='all_shortest_paths',
                label='academic_analysis'
            )
        except Exception as e:
            print(f"Citation path analysis failed: {e}")
        
        # 3. Predict future citations
        predictions = link_predictor.predict_links(
            graph=academic_citation_network,
            method='preferential_attachment',
            top_k=5
        )
        
        assert isinstance(predictions, list)
        
        # Track link prediction
        pred_id = tracker.track_link_prediction(
            graph=academic_citation_network,
            predictions=predictions,
            method='preferential_attachment',
            parameters={'top_k': 5},
            source='academic_analysis'
        )
        
        # 4. Analyze paper similarity
        query_paper = 'P2'  # "Attention Is All You Need"
        query_embedding = academic_embeddings[query_paper]
        
        similarities = sim_calc.batch_similarity(
            embeddings=academic_embeddings,
            query_embedding=query_embedding,
            method='cosine',
            top_k=5
        )
        
        assert isinstance(similarities, dict)
        
        # Track similarity analysis
        sim_id = tracker.track_similarity_calculation(
            embeddings=academic_embeddings,
            query_embedding=query_embedding,
            similarities=similarities,
            method='cosine',
            source='academic_analysis'
        )
        
        # 5. Analyze citation patterns by field
        nlp_papers = ['P1', 'P2', 'P3']
        graph_ml_papers = ['P4', 'P5', 'P6']
        cv_papers = ['P7', 'P8']
        
        # Create subgraphs for each field
        nlp_subgraph = academic_citation_network.subgraph(nlp_papers)
        graph_ml_subgraph = academic_citation_network.subgraph(graph_ml_papers)
        cv_subgraph = academic_citation_network.subgraph(cv_papers)
        
        # Calculate centrality for each field
        field_centralities = {}
        for field_name, subgraph in [('NLP', nlp_subgraph), ('Graph ML', graph_ml_subgraph), ('CV', cv_subgraph)]:
            if subgraph.number_of_nodes() > 0:
                subgraph_dict = {
                    'nodes': list(subgraph.nodes()),
                    'edges': list(subgraph.edges())
                }
                cent_result = centrality_calc.calculate_degree_centrality(subgraph_dict)
                field_centralities[field_name] = cent_result['centrality']
        
        # Verify field analysis
        assert len(field_centralities) > 0
        
        print(f"Academic citation analysis completed")
        print(f"PageRank top papers: {pagerank_result['rankings'][:3]}")
        print(f"Similar papers to {query_paper}: {list(similarities.keys())[:3]}")
        print(f"Field centralities: {list(field_centralities.keys())}")
    
    def test_social_media_influence_analysis(self, social_media_network):
        """Test social media influence analysis."""
        centrality_calc = CentralityCalculator()
        community_detector = CommunityDetector()
        conn_analyzer = ConnectivityAnalyzer()
        tracker = AlgorithmTrackerWithProvenance(provenance=True)
        
        # Convert to dict format
        graph_dict = {
            'nodes': list(social_media_network.nodes()),
            'edges': list(social_media_network.edges())
        }
        
        # 1. Calculate influence metrics
        degree_cent = centrality_calc.calculate_degree_centrality(graph_dict)
        betweenness_cent = centrality_calc.calculate_betweenness_centrality(graph_dict)
        
        # Track centrality analysis
        degree_id = tracker.track_centrality_calculation(
            graph=social_media_network,
            centrality_scores=degree_cent['centrality'],
            method='degree',
            source='social_influence_analysis'
        )
        
        betweenness_id = tracker.track_centrality_calculation(
            graph=social_media_network,
            centrality_scores=betweenness_cent['centrality'],
            method='betweenness',
            source='social_influence_analysis'
        )
        
        # 2. Detect communities (social circles)
        communities = community_detector.detect_communities(graph_dict, method='label_propagation')
        assert communities['algorithm'] == 'label_propagation'
        
        # Track community detection
        comm_id = tracker.track_community_detection(
            graph=social_media_network,
            communities=communities['communities'],
            method='label_propagation',
            source='social_influence_analysis'
        )
        
        # 3. Analyze connectivity
        components = conn_analyzer.find_connected_components(graph_dict)
        
        # Track connectivity analysis
        conn_id = tracker.track_connectivity_analysis(
            graph=social_media_network,
            components=components,
            method='connected_components',
            source='social_influence_analysis'
        )
        
        # 4. Identify influential users
        # Combine multiple centrality measures
        influence_scores = {}
        for user in social_media_network.nodes():
            degree_score = degree_cent['centrality'].get(user, 0)
            betweenness_score = betweenness_cent['centrality'].get(user, 0)
            
            # Combined influence score
            influence_scores[user] = 0.6 * degree_score + 0.4 * betweenness_score
        
        # Sort by influence
        influential_users = sorted(influence_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Track influence analysis
        influence_id = tracker.track_influence_analysis(
            graph=social_media_network,
            influence_scores=influence_scores,
            influential_users=influential_users[:5],
            method='combined_centrality',
            source='social_influence_analysis'
        )
        
        # 5. Analyze user attributes vs network position
        verified_users = [user for user, data in social_media_network.nodes(data=True) 
                          if data.get('verified', False)]
        
        verified_influence = {user: influence_scores.get(user, 0) for user in verified_users}
        non_verified_influence = {user: influence_scores.get(user, 0) 
                               for user in social_media_network.nodes() 
                               if user not in verified_users}
        
        # Track verification analysis
        verification_id = tracker.track_verification_analysis(
            graph=social_media_network,
            verified_influence=verified_influence,
            non_verified_influence=non_verified_influence,
            source='social_influence_analysis'
        )
        
        # Verify results
        assert len(influential_users) > 0
        assert len(communities['communities']) > 0
        assert len(components) > 0
        
        print(f"Social media influence analysis completed")
        print(f"Top influential users: {[user for user, score in influential_users[:3]]}")
        print(f"Number of communities: {len(communities['communities'])}")
        print(f"Connected components: {len(components)}")
        print(f"Verified users influence: {len(verified_users)}")
    
    def test_supply_chain_risk_analysis(self, supply_chain_network):
        """Test supply chain risk analysis."""
        path_finder = PathFinder()
        conn_analyzer = ConnectivityAnalyzer()
        tracker = AlgorithmTrackerWithProvenance(provenance=True)
        
        # Convert to dict format
        graph_dict = {
            'nodes': list(supply_chain_network.nodes()),
            'edges': list(supply_chain_network.edges())
        }
        
        # 1. Analyze supply chain paths
        # Find paths from suppliers to retailers
        suppliers = [node for node, data in supply_chain_network.nodes(data=True) 
                    if data['type'] == 'Supplier']
        retailers = [node for node, data in supply_chain_network.nodes(data=True) 
                    if data['type'] == 'Retailer']
        
        supply_paths = {}
        for supplier in suppliers:
            for retailer in retailers:
                try:
                    path = path_finder.dijkstra_shortest_path(supply_chain_network, supplier, retailer)
                    if path:
                        supply_paths[f"{supplier}->{retailer}"] = path
                except:
                    continue
        
        # Track path analysis
        path_id = tracker.track_supply_chain_paths(
            graph=supply_chain_network,
            supply_paths=supply_paths,
            method='dijkstra_shortest_path',
            source='supply_chain_risk_analysis'
        )
        
        # 2. Analyze connectivity and bottlenecks
        components = conn_analyzer.find_connected_components(graph_dict)
        
        # Track connectivity analysis
        conn_id = tracker.track_connectivity_analysis(
            graph=supply_chain_network,
            components=components,
            method='connected_components',
            source='supply_chain_risk_analysis'
        )
        
        # 3. Identify critical nodes (bottlenecks)
        node_betweenness = {}
        for node in supply_chain_network.nodes():
            # Simple betweenness approximation
            paths_through_node = 0
            for path in supply_paths.values():
                if node in path:
                    paths_through_node += 1
            node_betweenness[node] = paths_through_node
        
        # Sort by betweenness
        critical_nodes = sorted(node_betweenness.items(), key=lambda x: x[1], reverse=True)
        
        # Track bottleneck analysis
        bottleneck_id = tracker.track_bottleneck_analysis(
            graph=supply_chain_network,
            node_betweenness=node_betweenness,
            critical_nodes=critical_nodes[:5],
            method='path_count_betweenness',
            source='supply_chain_risk_analysis'
        )
        
        # 4. Analyze quality scores across the chain
        quality_scores = {}
        for node, data in supply_chain_network.nodes(data=True):
            quality_scores[node] = data.get('quality_score', 0.0)
        
        # Track quality analysis
        quality_id = tracker.track_quality_analysis(
            graph=supply_chain_network,
            quality_scores=quality_scores,
            source='supply_chain_risk_analysis'
        )
        
        # 5. Calculate lead time analysis
        lead_times = {}
        for edge in supply_chain_network.edges(data=True):
            source, target, data = edge
            lead_time = data.get('lead_time_days', 0)
            lead_times[f"{source}->{target}"] = lead_time
        
        # Track lead time analysis
        leadtime_id = tracker.track_lead_time_analysis(
            graph=supply_chain_network,
            lead_times=lead_times,
            source='supply_chain_risk_analysis'
        )
        
        # Verify results
        assert len(supply_paths) > 0
        assert len(critical_nodes) > 0
        assert len(quality_scores) > 0
        assert len(lead_times) > 0
        
        print(f"Supply chain risk analysis completed")
        print(f"Supply paths found: {len(supply_paths)}")
        print(f"Critical nodes: {[node for node, score in critical_nodes[:3]]}")
        print(f"Average quality score: {np.mean(list(quality_scores.values())):.2f}")
        print(f"Average lead time: {np.mean(list(lead_times.values())):.1f} days")
    
    def test_cross_domain_analysis(self, academic_citation_network, social_media_network, academic_embeddings):
        """Test cross-domain analysis combining academic and social networks."""
        sim_calc = SimilarityCalculator()
        tracker = AlgorithmTrackerWithProvenance(provenance=True)
        
        # 1. Find academic researchers in social network
        academic_users = []
        for node, data in social_media_network.nodes(data=True):
            interests = data.get('interests', [])
            if any(interest.lower() in ['research', 'academia', 'machine learning', 'ai'] for interest in interests):
                academic_users.append(node)
        
        # Track cross-domain identification
        cross_domain_id = tracker.track_cross_domain_analysis(
            academic_network=academic_citation_network,
            social_network=social_media_network,
            academic_users=academic_users,
            source='cross_domain_analysis'
        )
        
        # 2. Analyze topic similarity between academic papers and user interests
        # Map academic papers to social users based on content similarity
        paper_user_similarities = {}
        
        for paper_id, paper_embedding in academic_embeddings.items():
            paper_data = academic_citation_network.nodes[paper_id]
            paper_keywords = paper_data.get('keywords', [])
            
            for user_id in academic_users:
                user_data = social_media_network.nodes[user_id]
                user_interests = user_data.get('interests', [])
                
                # Simple similarity based on keyword overlap
                similarity_score = 0.0
                for keyword in paper_keywords:
                    for interest in user_interests:
                        if keyword.lower() in interest.lower() or interest.lower() in keyword.lower():
                            similarity_score += 1.0
                
                # Normalize
                max_possible = len(paper_keywords) * len(user_interests)
                if max_possible > 0:
                    similarity_score /= max_possible
                
                if similarity_score > 0:
                    paper_user_similarities[f"{paper_id}->{user_id}"] = similarity_score
        
        # Track similarity analysis
        similarity_id = tracker.track_cross_domain_similarity(
            paper_user_similarities=paper_user_similarities,
            method='keyword_overlap',
            source='cross_domain_analysis'
        )
        
        # 3. Identify potential collaborations
        # Find academic papers that might interest social media users
        collaboration_potential = {}
        
        for paper_id, paper_embedding in academic_embeddings.items():
            query_embedding = paper_embedding

            # Find similar papers
            similar_papers = sim_calc.batch_similarity(
                embeddings=academic_embeddings,
                query_embedding=query_embedding,
                method='cosine',
                top_k=3
            )

            # Map to users with matching interests (check all social network users)
            matching_users = []
            paper_data = academic_citation_network.nodes[paper_id]
            paper_keywords = paper_data.get('keywords', [])

            for user_id in social_media_network.nodes():
                user_data = social_media_network.nodes[user_id]
                user_interests = user_data.get('interests', [])

                if any(
                    keyword.lower() in interest.lower() or interest.lower() in keyword.lower()
                    for keyword in paper_keywords for interest in user_interests
                ):
                    matching_users.append(user_id)
            
            if matching_users:
                collaboration_potential[paper_id] = {
                    'similar_papers': list(similar_papers.keys()),
                    'matching_users': matching_users,
                    'avg_similarity': np.mean(list(similar_papers.values()))
                }
        
        # Track collaboration analysis
        collab_id = tracker.track_collaboration_potential(
            collaboration_potential=collaboration_potential,
            source='cross_domain_analysis'
        )
        
        # Verify results
        assert len(academic_users) > 0
        assert len(paper_user_similarities) > 0
        assert len(collaboration_potential) > 0
        
        print(f"Cross-domain analysis completed")
        print(f"Academic users found in social network: {len(academic_users)}")
        print(f"Paper-user similarities: {len(paper_user_similarities)}")
        print(f"Collaboration opportunities: {len(collaboration_potential)}")
    
    def test_performance_with_realistic_data(self, academic_citation_network, academic_embeddings):
        """Test performance with realistic data sizes."""
        import time
        
        # Test centrality calculation performance
        centrality_calc = CentralityCalculator()
        graph_dict = {
            'nodes': list(academic_citation_network.nodes()),
            'edges': list(academic_citation_network.edges())
        }
        
        start_time = time.time()
        pagerank_result = centrality_calc.calculate_pagerank(academic_citation_network)
        pagerank_time = time.time() - start_time
        
        # Test similarity calculation performance
        sim_calc = SimilarityCalculator()
        query_embedding = academic_embeddings['P2']
        
        start_time = time.time()
        similarities = sim_calc.batch_similarity(
            embeddings=academic_embeddings,
            query_embedding=query_embedding,
            method='cosine',
            top_k=5
        )
        similarity_time = time.time() - start_time
        
        # Test path finding performance
        path_finder = PathFinder()
        
        start_time = time.time()
        paths = path_finder.all_shortest_paths(academic_citation_network, 'P2')
        path_time = time.time() - start_time
        
        # Performance assertions
        assert pagerank_time < 1.0  # Should complete within 1 second
        assert similarity_time < 0.5  # Should complete within 0.5 seconds
        assert path_time < 0.5  # Should complete within 0.5 seconds
        
        print(f"Performance test results:")
        print(f"  PageRank calculation: {pagerank_time:.3f}s")
        print(f"  Similarity calculation: {similarity_time:.3f}s")
        print(f"  Path finding: {path_time:.3f}s")
        print(f"  Graph size: {academic_citation_network.number_of_nodes()} nodes, {academic_citation_network.number_of_edges()} edges")
        print(f"  Embeddings: {len(academic_embeddings)} papers")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
