"""Data loading components for neighbor sampling"""
from .dataloader import BlockSampler
from .. import sampling, subgraph, distributed

class MultiLayerNeighborSampler(BlockSampler):
    """Sampler that builds computational dependency of node representations via
    neighbor sampling for multilayer GNN.

    This sampler will make every node gather messages from a fixed number of neighbors
    per edge type.  The neighbors are picked uniformly.

    Parameters
    ----------
    fanouts : list[int] or list[dict[etype, int] or None]
        List of neighbors to sample per edge type for each GNN layer, starting from the
        first layer.

        If the graph is homogeneous, only an integer is needed for each layer.

        If None is provided for one layer, all neighbors will be included regardless of
        edge types.

        If -1 is provided for one edge type on one layer, then all inbound edges
        of that edge type will be included.
    replace : bool, default True
        Whether to sample with replacement
    return_eids : bool, default False
        Whether to return the edge IDs involved in message passing in the block.
        If True, the edge IDs will be stored as an edge feature named ``dgl.EID``.

    Examples
    --------
    To train a 3-layer GNN for node classification on a set of nodes ``train_nid`` on
    a homogeneous graph where each node takes messages from 5, 10, 15 neighbors for
    the first, second, and third layer respectively (assuming the backend is PyTorch):

    >>> sampler = dgl.dataloading.MultiLayerNeighborSampler([5, 10, 15])
    >>> collator = dgl.dataloading.NodeCollator(g, train_nid, sampler)
    >>> dataloader = torch.utils.data.DataLoader(
    ...     collator.dataset, collate_fn=collator.collate,
    ...     batch_size=1024, shuffle=True, drop_last=False, num_workers=4)
    >>> for blocks in dataloader:
    ...     train_on(blocks)

    If training on a heterogeneous graph and you want different number of neighbors for each
    edge type, one should instead provide a list of dicts.  Each dict would specify the
    number of neighbors to pick per edge type.

    >>> sampler = dgl.dataloading.MultiLayerNeighborSampler([
    ...     {('user', 'follows', 'user'): 5,
    ...      ('user', 'plays', 'game'): 4,
    ...      ('game', 'played-by', 'user'): 3}] * 3)
    """
    def __init__(self, fanouts, replace=False, return_eids=False):
        super().__init__(len(fanouts), return_eids)

        self.fanouts = fanouts
        self.replace = replace

    def sample_frontier(self, block_id, g, seed_nodes):
        fanout = self.fanouts[block_id]
        if isinstance(g, distributed.DistGraph):
            if fanout is None:
                # TODO(zhengda) There is a bug in the distributed version of in_subgraph.
                # let's use sample_neighbors to replace in_subgraph for now.
                frontier = distributed.sample_neighbors(g, seed_nodes, -1, replace=False)
            else:
                frontier = distributed.sample_neighbors(g, seed_nodes, fanout, replace=self.replace)
        else:
            if fanout is None:
                frontier = subgraph.in_subgraph(g, seed_nodes)
            else:
                frontier = sampling.sample_neighbors(g, seed_nodes, fanout, replace=self.replace)
        return frontier

class MultiLayerFullNeighborSampler(MultiLayerNeighborSampler):
    """Sampler that builds computational dependency of node representations by taking messages
    from all neighbors for multilayer GNN.

    This sampler will make every node gather messages from every single neighbor per edge type.

    Parameters
    ----------
    n_layers : int
        The number of GNN layers to sample.
    return_eids : bool, default False
        Whether to return the edge IDs involved in message passing in the block.
        If True, the edge IDs will be stored as an edge feature named ``dgl.EID``.

    Examples
    --------
    To train a 3-layer GNN for node classification on a set of nodes ``train_nid`` on
    a homogeneous graph where each node takes messages from all neighbors for the first,
    second, and third layer respectively (assuming the backend is PyTorch):

    >>> sampler = dgl.dataloading.MultiLayerFullNeighborSampler(3)
    >>> collator = dgl.dataloading.NodeCollator(g, train_nid, sampler)
    >>> dataloader = torch.utils.data.DataLoader(
    ...     collator.dataset, collate_fn=collator.collate,
    ...     batch_size=1024, shuffle=True, drop_last=False, num_workers=4)
    >>> for blocks in dataloader:
    ...     train_on(blocks)
    """
    def __init__(self, n_layers, return_eids=False):
        super().__init__([None] * n_layers, return_eids=return_eids)
