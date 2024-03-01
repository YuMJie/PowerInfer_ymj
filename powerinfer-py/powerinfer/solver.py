#!/usr/bin/env python
# coding=utf-8
import argparse
from cvxopt.glpk import ilp
import numpy as np
from cvxopt import matrix
import torch
import pickle

def solve_gpu_split(
    activation_path: str,
    neuron: int,
    capacity: int,
    layer: int,
    batch: int,
    threshold: int,
):
    print("neuron", neuron)
    print("capacity", capacity)
    print("layer", layer)
    print("batch", batch)
    print("threshold", threshold)
    
    # Processing activation data
    values = []
    for i in range(layer): #0-31
        # Load and sort activation data for each layer
        freq = torch.load(f"{activation_path}/activation_{i}.pt")
        # print("freq", freq.shape) # 11008
        freq, _ = torch.sort(freq, descending=True)
        # print(f"Layer {i} Activation: {freq[:10]}")
        freq = freq * -1.0
        freq = freq.view(-1, batch)
        # print("freq1", freq.shape) # 43, 256 

        freq = freq.sum(dim=1)
        # print("freq2", freq.shape) # 43
        # print(f"Layer {i} Activation: {freq[:10]}")

        freq = freq.tolist()
        values += freq
        # print("values", values)
    # Padding zero values for additional constraints
    for i in range(layer):
        values += [0.0]
    c = np.array(values, dtype=float)#优化目标的系数 
    c = matrix(c)
    # print("c的维度", c.size) #1408 ，1 
    # Setting capacity and neuron count per batch
    CAP = capacity
    CAP = int(CAP / batch)
    neuron = int(neuron / batch)
    coeff = [] #约束条件的系数
    h = []  #约束条件的右边的值

    # Constraint 1: Total neuron activation constraint
    lst = []
    for i in range(neuron * layer):
        lst.append(1)
    for i in range(layer):
        lst.append(0)
    coeff.append(lst)
    h.append(CAP)
    # print(lst)
    # Constraint 2: Threshold constraint for GPU split per layer
    for i in range(layer):
        lst = [0] * (neuron * layer + layer)# 维度为1408
        for j in range(neuron):
            lst[i * neuron + j] = -1
        lst[neuron * layer + i] = int(threshold / batch)
        coeff.append(lst)
        h.append(0)

    # Constraint 3: Upper bound on neuron activations
    for i in range(layer):
        lst = [0] * (neuron * layer + layer)
        for j in range(neuron):
            lst[i * neuron + j] = 1
        lst[neuron * layer + i] = -1000000  # Arbitrary large negative number as an upper bound
        coeff.append(lst)
        h.append(0)

    # Convert lists to matrix format for ILP solver
    coeff = np.array(coeff, dtype=float)
    # print(coeff)
    G = matrix(coeff)
    h = np.array(h, dtype=float)
    h = matrix(h)

    # Define the set of integer and binary variables
    I = set(range(neuron * layer + layer))
    B = set()

    # Solving the ILP problem
    (status, x) = ilp(c, G, h, None, None, B, I, options={'tm_lim' : 30000}) # with 30s timeout
    print(f"ILP Status: {status}")
    ans = list(x)
    print(f"Total Activation Units: {sum(ans)}")

    aligned_lst = []
    for i in range(layer):
        aligned_lst.append(sum(ans[i * neuron:i * neuron + neuron] * batch))

    return aligned_lst
