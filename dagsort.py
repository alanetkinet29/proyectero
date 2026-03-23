#! /usr/bin/env python3
# -*- coding: utf-8 -*-

from collections import defaultdict

class Graph:
    # Gemini generated code for topological sort
    # using DFS method
    
    """
    def example():
        g = Graph(8)
        
        g.add_edge(4, 2)
        g.add_edge(0, 7)
        g.add_edge(0, 5)
        g.add_edge(4, 0)
        g.add_edge(1, 7)
        g.add_edge(5, 6)
        g.add_edge(2, 3)
        g.add_edge(0, 3)
        g.add_edge(3, 1)

        print("Following is a Depth First Traversal (DFS) based Topological Sort:")
        # The result will be one valid topological order (e.g., [5, 4, 2, 3, 1, 0] or similar)
        print(g.topological_sort())
    """
    
    def __init__(self, vertices):
        self.graph = defaultdict(list)  # Dictionary to store the graph (adjacency list)
        self.V = vertices               # Number of vertices

    def add_edge(self, u, v):
        """Add a directed edge from u to v."""
        self.graph[u].append(v)

    def dfs_sort(self, v, visited, stack):
        """Recursive helper function for DFS and topological sorting."""
        visited[v] = True

        # Recur for all the vertices adjacent to this vertex
        for neighbor in self.graph[v]:
            if not visited[neighbor]:
                self.dfs_sort(neighbor, visited, stack)

        # Push current vertex to stack after all its neighbors (dependencies) are visited
        stack.insert(0, v) # Can also use stack.append(v) and reverse later

    def topological_sort(self):
        """Performs a topological sort of the DAG."""
        # Mark all the vertices as not visited
        visited = {i: False for i in range(self.V)}
        stack = []

        # Call the recursive helper function for all unvisited nodes
        for i in range(self.V):
            if not visited[i]:
                self.dfs_sort(i, visited, stack)

        return stack
