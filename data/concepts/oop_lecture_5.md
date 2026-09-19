# Lecture 5: Abstract Classes and Interfaces

**Course:** CS3301 Object-Oriented Analysis and Design  
**Department:** Computer Science and Engineering, CEG Anna University

---

## 1. Ground Truth Invariants

### Invariant 1: Abstract Classes Cannot Be Instantiated
- An abstract class CAN have constructors, concrete methods, and fields — but you CANNOT create an instance of it directly with `new`.
- The constructor of an abstract class runs when a concrete subclass calls `super()`. It initialises the abstract class's portion of the object.
- An abstract class can have zero abstract methods. It is still abstract if declared so, and still cannot be instantiated.

### Invariant 2: Interfaces Define Contracts, Not Implementations
- An interface declares method signatures that implementing classes MUST provide (prior to Java 8 default methods).
- A class can implement MULTIPLE interfaces — this is how Java achieves a form of multiple inheritance without the Diamond Problem of classes.
- Since Java 8, interfaces can have `default` methods (with a body), but these are meant as backward-compatible additions, NOT as a replacement for abstract classes.

### Invariant 3: Abstract Class vs Interface — When to Use Which
- Use an abstract class when subclasses share common state (fields) or implementation and form a genuine IS-A hierarchy.
- Use an interface when you want to define a capability contract that unrelated classes can implement (e.g., `Comparable`, `Serializable`).
- A class can extend only ONE abstract class but implement MANY interfaces.

---

## 2. Common Fallacy Patterns (Known Misconceptions)

### `ABSTRACT_CLASS_HAS_NO_CONSTRUCTOR`
- **Description:** Student believes abstract classes cannot have constructors.
- **Example flawed claim:** *Since you can't create an object of an abstract class, it has no constructor.*
- **Pedagogical counter:** Try this: write an abstract class with a constructor that prints "init". Then extend it. When you create the subclass, your print runs. The abstract class's constructor initialises ITS fields via `super()`. Without it, who initialises the parent's private fields?

### `INTERFACE_EQUALS_ABSTRACT_CLASS`
- **Description:** Student sees no difference between an interface and an abstract class.
- **Example flawed claim:** *An interface is just an abstract class with all abstract methods.*
- **Pedagogical counter:** A class can extend only one abstract class but implement many interfaces. An abstract class can have state (fields), constructors, and concrete methods. An interface (pre-Java 8) has none of these. They serve different architectural roles: IS-A hierarchy vs cross-cutting contract.

### `DEFAULT_METHODS_MAKE_INTERFACES_CLASSES`
- **Description:** Student believes Java 8 default methods eliminate the difference between interfaces and abstract classes.
- **Example flawed claim:** *Now that interfaces can have method bodies, they're basically abstract classes.*
- **Pedagogical counter:** Interfaces still cannot have instance fields or constructors. Default methods exist for backward compatibility — adding a method to an existing interface without breaking all implementors. An abstract class manages object state; an interface defines a contract.

---

## 3. Lecture Notes

Abstract classes sit between concrete classes and interfaces. An **abstract class** is declared with the `abstract` keyword and may contain both abstract (no body) and concrete (with body) methods. You cannot instantiate it directly — it serves as a base for subclasses.

A common misconception is that abstract classes have no constructors. They do. The constructor runs when a concrete subclass is instantiated via `super()`. It initialises the abstract class's fields.

**Interfaces** define a contract: a set of method signatures that any implementing class must provide. Before Java 8, interfaces were purely abstract — no method bodies, no fields (only `public static final` constants). Java 8 added `default` methods to allow interface evolution without breaking existing implementors.

The critical architectural choice: **abstract class vs interface**. Use abstract classes when classes share a common implementation and form an IS-A hierarchy (e.g., `Shape` → `Circle`, `Rectangle`). Use interfaces when unrelated classes share a capability (e.g., `Comparable` can be implemented by `String`, `Integer`, `Student`).

---

## 4. Lecture Transcript (Excerpt)

> "Students always ask: if both can have method bodies now, what's the difference? Here's the difference — try adding an `int count` field to an interface. You can't. Interfaces don't manage state. Abstract classes do. And you can extend only one class, but implement ten interfaces. These are architectural constraints that shape your design. Default methods were added so Oracle could add `forEach()` to the `Iterable` interface without breaking every Java program ever written."

---

## 5. Opening Question

Hey! Can you explain what happens when a concrete class extends an abstract class — specifically, does the abstract class's constructor ever run?
