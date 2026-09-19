# Concept Invariants: Linked Lists vs. Arrays

**Course:** CS3251 Data Structures and Algorithms  
**Department:** Computer Science and Engineering, CEG Anna University

---

## 1. Ground Truth Invariants

### Invariant 1: Memory Layout and Access Time
- Arrays store elements in contiguous memory. Index access is O(1): address(i) = base + i * element_size, computed directly.
- Linked lists store nodes at arbitrary locations connected by pointers. To access element i, you MUST traverse i nodes from the head: O(n).
- A linked list does NOT support O(1) random access regardless of implementation.

### Invariant 2: Insertion and Deletion
- Inserting in the middle of an array requires shifting all subsequent elements: O(n).
- Inserting in the middle of a linked list (given a pointer to the predecessor) changes two pointers: O(1). But FINDING the predecessor still requires O(n) traversal.
- Inserting at the HEAD of a singly linked list is O(1). Inserting at the TAIL requires traversal unless a tail pointer is maintained.

### Invariant 3: Memory Overhead
- Each linked list node stores data PLUS one or more pointers (8 bytes each on 64-bit). A linked list of integers uses MORE memory per element than an int array.
- Arrays may waste capacity due to pre-allocation. Linked lists allocate exactly one node per element but always pay the pointer overhead.

---

## 2. Common Fallacy Patterns (Known Misconceptions)

### `LINKED_LIST_IS_FASTER_ALWAYS`
- **Description:** Student believes linked lists are generally faster than arrays for all operations.
- **Example flawed claim:** *Linked lists are faster because you never need to shift elements.*
- **Pedagogical counter:** Accessing array[500] hits L1 cache in nanoseconds because elements are contiguous. For a linked list, each pointer dereference is a potential cache miss. Even if deletion is O(1) by pointer count, 1000 cache misses can be slower than shifting 1000 elements that fit in a single cache line.

### `LINKED_LIST_RANDOM_ACCESS_IS_FAST`
- **Description:** Student believes accessing linked list elements by index is fast.
- **Example flawed claim:** *Accessing the 100th element in a linked list is fast since we just follow pointers.*
- **Pedagogical counter:** Following a pointer chain of 100 nodes means 100 sequential memory reads, each potentially a cache miss. To get element 1000, you must follow 1000 pointers. How does that compare to one multiply-and-add operation for an array?

### `ARRAY_INSERTION_IS_ALWAYS_O1`
- **Description:** Student believes all array insertions are O(1).
- **Example flawed claim:** *Inserting into an array is O(1) since arrays have direct access.*
- **Pedagogical counter:** Direct address calculation for READING is O(1). But inserting at position 0 in a 1-million element array requires shifting 1 million elements. Appending at the END is amortised O(1) with dynamic resizing, but insertion in the MIDDLE is O(n).
