# Lecture 4: Polymorphism — Overloading vs Overriding

**Course:** CS3301 Object-Oriented Analysis and Design  
**Department:** Computer Science and Engineering, CEG Anna University

---

## 1. Ground Truth Invariants

### Invariant 1: Runtime Polymorphism (Dynamic Dispatch)
- Method overriding achieves RUNTIME polymorphism. When a parent reference holds a child object and the child overrides a method, calling that method dispatches to the CHILD's implementation at runtime — not the parent's.
- The JVM uses the actual object type (not the declared reference type) to resolve overridden instance methods.
- A cast to the parent type does NOT change which overriding method is called.

### Invariant 2: Compile-Time Polymorphism (Method Overloading)
- Method overloading is COMPILE-TIME (static) polymorphism: the compiler selects which method version to call based on the declared argument types at compile time.
- Overloaded methods have the same name but different parameter lists (different types or different count).
- Overloading and overriding are fundamentally different mechanisms with different timing (compile vs runtime).

### Invariant 3: Reference Type vs Object Type
- The reference type determines which methods are VISIBLE at compile time.
- The object type determines which overridden method body EXECUTES at runtime.
- `Animal a = new Dog();` — `a` can only call methods declared in `Animal`, but if Dog overrides one, Dog's version runs.

---

## 2. Common Fallacy Patterns (Known Misconceptions)

### `OVERLOADING_EQUALS_OVERRIDING`
- **Description:** Student conflates method overloading (compile-time) with method overriding (runtime).
- **Example flawed claim:** *When I define add(int) and add(double) in the same class, that is overriding.*
- **Pedagogical counter:** Overloading is two different methods sharing a name in the SAME class, resolved by the compiler. Overriding is a child class replacing a parent method, resolved at runtime. If they were the same, why would the language have two different words?

### `POLYMORPHISM_ONLY_WORKS_WITH_CASTING`
- **Description:** Student believes you must cast to a child type to invoke the overriding child method.
- **Example flawed claim:** *To call Dog's speak() method, I must cast Animal a to Dog first.*
- **Pedagogical counter:** If `Animal a = new Dog()` and Dog overrides `speak()`, calling `a.speak()` dispatches to Dog's version WITHOUT any cast. Casting is only needed to access methods that exist ONLY in Dog and are not declared in Animal.

### `OVERRIDING_CHANGES_WITH_CAST`
- **Description:** Student believes casting a child to parent type changes which overriding method runs.
- **Example flawed claim:** *If I cast my Dog to Animal, calling speak() will now call Animal's speak().*
- **Pedagogical counter:** Dynamic dispatch is based on the actual heap object, not the reference type. The object IS a Dog regardless of what type the variable is declared as. Casting affects compile-time visibility, not runtime dispatch.

---

## 3. Lecture Notes

Polymorphism means "many forms" — the same method call can behave differently depending on the object it's invoked on. Java supports two kinds:

**Compile-time (static) polymorphism** via method overloading. The compiler sees `add(int)` and `add(double)` as two separate methods. It picks the right one based on the argument types at compile time.

**Runtime (dynamic) polymorphism** via method overriding. When a subclass provides its own implementation of a method declared in the parent, the JVM dispatches to the child's version at runtime. This is the power of polymorphism: `Animal a = new Dog(); a.speak();` calls Dog's `speak()` even though the reference type is Animal.

The key insight is the separation between **reference type** and **object type**. The reference type (`Animal`) controls what methods are visible at compile time. The object type (`Dog`) controls which method body runs. Casting to `Animal` does NOT change the fact that the object in memory is a Dog.

---

## 4. Lecture Transcript (Excerpt)

> "Let me write this on the board: `Animal a = new Dog(); a.speak();` — which speak() runs? If you said Animal's, you fell into the trap. The JVM looks at what the object actually IS on the heap, not what the variable type says. The object IS a Dog, so Dog's speak() runs. This is dynamic dispatch. Now, do you need to cast `a` to Dog to get Dog's speak()? No! The cast is only needed if Dog has a method that Animal doesn't declare at all."

---

## 5. Opening Question

Hey! If I write `Animal a = new Dog()` and both classes have a `speak()` method, which version gets called and why?
