---
# Live Test: Binary Search Trees

**Course:** Computer Science
**Department:** Computer Science & Engineering

---

## 1. Ground Truth Invariants

### Invariant 1: BST Property
- For every node X in a Binary Search Tree (BST), all keys in the left subtree of X are strictly less than X.key, and all keys in the right subtree of X are strictly greater than X.key.

### Invariant 2: Inorder Traversal
- An **inorder traversal** (Left, Root, Right) of a valid BST always produces a strictly **monotonic increasing** sorted sequence.

### Invariant 3: AVL Balance Factor
- The **balance factor** of a node is defined as the height of its left subtree minus the height of its right subtree. The balance factor must always be in the set {-1, 0, 1}.

### Invariant 4: AVL Tree Rotations
- **Single and double rotations** in AVL trees maintain the BST invariant while restoring the O(log N) worst-case search height.

---


---

## 2. Common Fallacy Patterns (Known Misconceptions)

### `BST_ALLOWS_DUPLICATES`
- **Description:** Students often believe that a BST can contain duplicate keys, violating the strict ordering invariant.
- **Example flawed claim:** *I think a BST can have duplicate keys as long as they are in different subtrees.*
- **Pedagogical counter:** If you have two nodes with the same key, where would you place the second node without violating the BST property?

### `INORDER_TRAVERSAL_SORTED_BUT_NOT_STRICTLY`
- **Description:** Students may think that an inorder traversal of a BST produces a non-strictly increasing sequence, allowing duplicates.
- **Example flawed claim:** *An inorder traversal gives a sorted list, but it can have duplicates if the BST allows them.*
- **Pedagogical counter:** If an inorder traversal produced a sequence with duplicates, how would that affect the BST property for the nodes involved?

### `AVL_BALANCE_FACTOR_OUT_OF_RANGE`
- **Description:** Students might believe that the balance factor in an AVL tree can be outside the range of {-1, 0, 1}.
- **Example flawed claim:** *I think the balance factor can be 2 or -2 sometimes, as long as the tree is still balanced.*
- **Pedagogical counter:** If the balance factor were 2, how would that affect the height of the tree and the efficiency of search operations?
## 3. Lecture Notes

A **Binary Search Tree (BST)** is a fundamental data structure that maintains a specific ordering property, which allows for efficient search, insertion, and deletion operations. The core invariant of a BST ensures that for any given node, all keys in the left subtree are strictly less than the node's key, and all keys in the right subtree are strictly greater. This property enables efficient searching with a time complexity of O(log N) in the average case, assuming the tree is balanced.

An **inorder traversal** of a BST, which visits nodes in the order Left, Root, Right, produces a strictly increasing sequence of keys. This traversal is often used to verify the correctness of a BST and to retrieve keys in a sorted order. The **balance factor** of a node in an AVL tree, a type of self-balancing BST, is a critical metric that ensures the tree remains balanced. The balance factor must be within {-1, 0, 1} to maintain the O(log N) height property. **Rotations** are used to restore the balance factor when it is violated, ensuring that the tree remains balanced and efficient for operations.

---

## 4. Lecture Transcript (Excerpt)

> "The **Binary Search Tree (BST)** invariant is crucial for understanding how BSTs operate. For any node, all keys in the left subtree must be strictly less than the node's key, and all keys in the right subtree must be strictly greater. This property ensures that search operations are efficient. Additionally, an **inorder traversal** of a BST will always produce a sorted sequence, which is a powerful feature for retrieving data in order. In AVL trees, the **balance factor** must be maintained within {-1, 0, 1} to keep the tree balanced. **Rotations** are used to restore this balance, ensuring that the tree remains efficient for all operations."

---

## 5. Opening Question

Hey! If you insert a duplicate key into a BST, where should it go and why?
