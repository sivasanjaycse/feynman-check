# Lecture 6: Exception Handling

**Course:** CS3301 Object-Oriented Analysis and Design  
**Department:** Computer Science and Engineering, CEG Anna University

---

## 1. Ground Truth Invariants

### Invariant 1: Exception Hierarchy
- All exceptions extend `Throwable`. Under it: `Error` (JVM-level, not catchable in practice) and `Exception`.
- `RuntimeException` and its subclasses are UNCHECKED — the compiler does not force you to handle them.
- All other `Exception` subclasses are CHECKED — the compiler forces either a `catch` block or a `throws` declaration.

### Invariant 2: try-catch-finally Execution
- The `finally` block ALWAYS executes, whether an exception was thrown or not, whether it was caught or not.
- If both `catch` and `finally` contain a `return`, the `finally` return OVERRIDES the `catch` return.
- An exception in the `finally` block itself replaces the original exception — the original is lost unless explicitly preserved.

### Invariant 3: throw vs throws
- `throw` is a statement that actually throws an exception object at runtime: `throw new IllegalArgumentException("bad");`
- `throws` is a method signature declaration that warns callers: this method MAY throw this checked exception.
- `throw` happens inside the method body. `throws` goes in the method header. They are complementary, not interchangeable.

---

## 2. Common Fallacy Patterns (Known Misconceptions)

### `FINALLY_SKIPPED_ON_EXCEPTION`
- **Description:** Student believes finally does not run if an exception occurs.
- **Example flawed claim:** *If an exception is thrown, finally is skipped because the program jumps to catch.*
- **Pedagogical counter:** Write `try { throw new Exception(); } catch(Exception e) { System.out.println("caught"); } finally { System.out.println("finally"); }`. Both "caught" AND "finally" print. Finally runs AFTER catch, regardless of what happened.

### `THROW_EQUALS_THROWS`
- **Description:** Student treats `throw` and `throws` as identical.
- **Example flawed claim:** *`throws` in the method signature is what actually throws the exception.*
- **Pedagogical counter:** Remove the `throw new X()` statement from your method body but keep `throws X` in the signature. Does the exception ever get thrown? No. `throws` is a declaration to the compiler. `throw` is the runtime action. One is a promise, the other is the act.

### `CATCH_ALL_IS_SAFE`
- **Description:** Student believes catching `Exception` (or `Throwable`) broadly is good practice.
- **Example flawed claim:** *I always write `catch(Exception e)` to make sure nothing crashes.*
- **Pedagogical counter:** If you catch all exceptions, you silently swallow `NullPointerException`, `ArrayIndexOutOfBoundsException`, and other bugs that should crash loudly so you can fix them. Catching too broadly hides real bugs. Catch specific exceptions you can actually handle.

---

## 3. Lecture Notes

Exception handling separates error-handling logic from normal program flow. Java's exception hierarchy starts at `Throwable`, splitting into `Error` (out-of-memory, stack overflow — don't catch these) and `Exception`.

**Checked exceptions** (subclasses of `Exception` but NOT `RuntimeException`) must be declared in the method's `throws` clause or caught in a `try-catch`. The compiler enforces this. **Unchecked exceptions** (`RuntimeException` subclasses like `NullPointerException`) don't require explicit handling.

The `try-catch-finally` construct works as follows: code in `try` is monitored, if an exception occurs the matching `catch` handles it, and `finally` runs regardless — even if no exception occurred, even if `catch` re-throws, even if `catch` returns a value. The only thing that prevents `finally` from running is `System.exit()`.

A subtle pitfall: if `finally` has a `return` statement, it overrides any return from `try` or `catch`. This is legal but dangerous — the original return value or exception is silently replaced.

---

## 4. Lecture Transcript (Excerpt)

> "Here's the exam question that catches everyone: does `finally` run if there's a return in the try block? Yes. Does it run if an exception is thrown? Yes. Does it run if the exception is NOT caught? Still yes — finally runs and THEN the exception propagates. The only way to skip finally is `System.exit()`. And here's the cruel part — if finally also has a return, it replaces whatever the try block was returning. Never put a return in finally."

---

## 5. Opening Question

Hey! What exactly is the difference between `throw` and `throws` in Java, and when would you use each one?
