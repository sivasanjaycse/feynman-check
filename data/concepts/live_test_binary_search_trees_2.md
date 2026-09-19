---
# Live Test: Binary Search Trees

**Course:** Computer Science
**Department:** Computer Science & Engineering

---

## 1. Ground Truth Invariants

### Invariant 1: BST Property
- For every node X in a Binary Search Tree (BST), all keys in the left subtree of X are strictly less than X.key.
- All keys in the right subtree of X are strictly greater than X.key.

### Invariant 2: Inorder Traversal
- An inorder traversal (Left, Root, Right) of a valid BST always produces a strictly monotonic increasing sorted sequence.

### Invariant 3: AVL Balance Factor
- The balance factor of a node is defined as height(left) - height(right) and must be in the set {-1, 0, 1}.
- Single and double rotations maintain the BST invariant while restoring O(log N) worst-case search height.

### Invariant 4: AVL Tree Rotations
- AVL tree rotations (single and double) are used to maintain the balance factor within the required range.
- These rotations ensure that the BST property is preserved while rebalancing the tree.

---


---

## 2. Common Fallacy Patterns (Known Misconceptions)

### `BST_ALLOWS_DUPLICATES`
- **Description:** Students often believe that a BST can contain duplicate keys, violating the strict ordering invariant.
- **Example flawed claim:** *I think it's okay to have duplicate keys in a BST as long as they are in the same subtree.*
- **Pedagogical counter:** If you insert a duplicate key into a BST, how would the tree maintain the strict ordering property for all operations?

### `INORDER_TRAVERSAL_SORTED_BUT_NOT_STRICTLY`
- **Description:** Students may think that an inorder traversal of a BST produces a non-strictly increasing sequence, allowing for duplicates.
- **Example flawed claim:** *An inorder traversal of a BST gives a sorted list, but it can have duplicates if the tree allows them.*
- **Pedagogical counter:** If an inorder traversal produced a sequence with duplicates, how would that affect the BST property for the nodes involved?

### `AVL_BALANCE_FACTOR_ALLOWS_OTHER_VALUES`
- **Description:** Students might believe that the balance factor in an AVL tree can be any integer, not just -1, 0, or 1.
- **Example flawed claim:** *The balance factor in an AVL tree can be any number, as long as it's not too large.*
- **Pedagogical counter:** If the balance factor could be any integer, how would that impact the worst-case time complexity of search operations in an AVL tree?
## 3. Lecture Notes

A **Binary Search Tree (BST)** is a fundamental data structure that maintains a specific order among its elements. The core invariant of a BST ensures that for any given node, all keys in the left subtree are less than the node's key, and all keys in the right subtree are greater. This property allows for efficient search, insertion, and deletion operations with an average time complexity of O(log N) for balanced trees.

**Inorder traversal** of a BST, which visits nodes in the order Left, Root, Right, produces a strictly increasing sequence of keys. This traversal is often used to retrieve all elements of the BST in a sorted order. **AVL trees** are a type of self-balancing BST that maintain a balance factor of -1, 0, or 1 for every node. The balance factor is calculated as the height of the left subtree minus the height of the right subtree. If the balance factor falls outside this range, rotations are performed to rebalance the tree, ensuring that the worst-case time complexity for search, insertion, and deletion operations remains O(log N).

---

## 4. Lecture Transcript (Excerpt)

> "In a Binary Search Tree, the most critical invariant is that for any node, all keys in the left subtree must be strictly less than the node's key, and all keys in the right subtree must be strictly greater. This property is what allows us to perform efficient search operations. Additionally, an inorder traversal of a BST will always yield a sorted sequence of keys. For AVL trees, we introduce a balance factor to ensure the tree remains balanced. The balance factor must be -1, 0, or 1, and if it deviates from this, we perform rotations to restore balance while maintaining the BST property."

---

## 5. Opening Question

Hey! Can you explain how a BST ensures that all keys are in a specific order and what happens if duplicates are allowed?
