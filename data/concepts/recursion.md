# Concept Invariants: Recursion vs. Iteration

**Course:** CS3251 Fundamentals of Computing and Programming  
**Department:** Computer Science and Engineering, CEG Anna University

---

## 1. Ground Truth Invariants

### Invariant 1: Call Stack and Stack Overflow
- Every recursive call pushes a new activation record (stack frame) onto the call stack.
- The call stack has a fixed maximum depth. Without a reached base case, recursion exhausts the stack and throws StackOverflowError.
- StackOverflowError terminates the program abruptly; it does NOT run forever in the background.

### Invariant 2: Base Case Requirement
- Every recursive function MUST have at least one base case: a condition under which it returns directly without a further recursive call.
- A base case that is unreachable for certain inputs is equivalent to having no base case for those inputs.

### Invariant 3: Tail Recursion vs. Head Recursion
- Tail recursion: the recursive call is the LAST operation. Some runtimes optimise this into iteration.
- Head recursion: work happens AFTER the recursive call returns. Cannot be trivially optimised.
- Python does NOT perform tail-call optimisation.

---

## 2. Common Fallacy Patterns (Known Misconceptions)

### `RECURSION_RUNS_SIMULTANEOUSLY`
- **Description:** Student believes recursive calls run in parallel.
- **Example flawed claim:** *When factorial(5) calls factorial(4), both are running at the same time.*
- **Pedagogical counter:** factorial(5) cannot compute 5 * result until factorial(4) has COMPLETELY returned. If both ran at the same time, who provides the return value factorial(5) is waiting for?

### `BASE_CASE_IS_OPTIONAL`
- **Description:** Student believes a recursive function can work without a base case.
- **Example flawed claim:** *For small inputs the recursion just naturally stops.*
- **Pedagogical counter:** Trace f(n) = f(n-1) with n=2: calls f(1), calls f(0), calls f(-1)... When does it stop? Without an explicit return condition, the stack grows until the program crashes.

### `RECURSION_ALWAYS_SLOWER`
- **Description:** Student believes recursion is always less efficient than iteration.
- **Example flawed claim:** *Recursion is always slow because of the extra function calls.*
- **Pedagogical counter:** Merge Sort and Quicksort are recursive and outperform naive iterative sorting. For balanced recursion the call stack is O(log n) deep. An iterative tree traversal must manually manage a stack data structure — doing the same work explicitly with extra complexity.

### `STACK_OVERFLOW_MEANS_INFINITE_LOOP`
- **Description:** Student conflates StackOverflowError with an infinite loop.
- **Example flawed claim:** *If there is a StackOverflowError, the program is stuck in an infinite loop.*
- **Pedagogical counter:** An infinite loop runs indefinitely but consumes no additional stack memory. A StackOverflowError terminates the program after a bounded number of frames. These have opposite behaviours: one never terminates, the other terminates immediately.
