"""Implementation of discrimination trees."""

import sys


class DiscTree:
  """A node of a discrimination tree."""

  def __init__(self, index, parent, var_test=None):
    self.index = index
    self.parent = parent
    self.var_test = var_test
    assert var_test
    self.leaves = []
    self.interiors = []
    self.ints = {}

  def __str__(self):
    return '<DiscTree %s>' % (self.index,)

  def __repr__(self):
    return '<DiscTree %s>' % (self.index,)

  def child_matching_index(self, index):
    "Returns the child node with the specified index, or None."
    return self.ints.get(index, None)

  def printt(self, depth=0):
    sys.stdout.write(" " * (depth * 2))
    print len(self.interiors), len(self.leaves)
    for i in self.interiors:
      i.printt(depth + 1)

  def is_variable(self, sym):
    return self.var_test(sym)

  def retrieve(self, path):
    """Yields all propositions in this tree matching the specified
    path.
    """
    if len(path) == 0:
      for leaf in self.leaves:
        yield leaf
    else:
      next_index = path[0]
      if self.is_variable(next_index):
        for leaf in self.retrieve_variable(path[1:]):
          yield leaf
      else:
        next_disc_tree = self.child_matching_index(next_index)
        if next_disc_tree == None:
          return
        else:
          for leaf in next_disc_tree.retrieve(path[1:]):
            yield leaf

  def position(self, path):
    if len(path) == 0:
      return self
    else:
      next_disc_tree = self.child_matching_index(path[0])
      if next_disc_tree == None:
        return None
      else:
        return next_disc_tree.position(path[1:])

  def retrieve_variable(self, path):
    for child in self.interiors:
      for leaf in child.retrieve(path):
        yield leaf

  def put(self, path, leaf):
    """Inserts leaf into the tree at the node specified by the
    path.
    """
    if len(path) == 0:
      if isinstance(leaf, DiscTree):
        self.interiors.append(leaf)
        self.ints[leaf.index] = leaf
      else:
        self.leaves.append(leaf)
      return True
    else:
      next_index = path[0]
      next_disc_tree = self.child_matching_index(next_index)
      if next_disc_tree == None:
        next_disc_tree = DiscTree(next_index, self, var_test=self.var_test)
        self.interiors.append(next_disc_tree)
        self.ints[next_disc_tree.index] = next_disc_tree
      next_disc_tree.put(path[1:], leaf)

  def erase(self, path):
    leaf_parent = self.position(path)
    if leaf_parent != None:
      leaf_parent.erase_at()
    return False

  def erase_at(self):
    """Deletes an entire tree from the parent."""
    for child in self.interiors:
      child.erase_at()
    if self.parent != None:
      self.parent.interiors.remove(self)
      del self.parent.ints[self.index]
    return True

  def dump(self, stream=sys.stdout, indent=0):
    """Dumps a printed representation of a complete tree."""
    stream.write('\n' + ' ' * indent + str(self))
    for child in self.leaves:
      stream.write('\n' + ' ' * (indent + 3) + str(child))
    for child in self.interiors:
      child.dump(stream=stream, indent=indent + 3)


def make_root_disc_tree(var_test=None):
  """Creates and returns a brand new root node."""
  return DiscTree("ROOT", None, var_test=var_test)
