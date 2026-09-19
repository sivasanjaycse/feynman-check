# Lecture 3: Inheritance — IS-A vs HAS-A

**Course:** CS3301 Object-Oriented Analysis and Design  
**Department:** Computer Science and Engineering, CEG Anna University

---

## 1. Ground Truth Invariants

### Invariant 1: Inheritance Models IS-A
- Inheritance (`extends`) models an IS-A relationship: a subclass IS a specialised form of the parent.
- This means any code that works with the parent type must also work correctly with the child type (Liskov Substitution Principle).
- Inheritance creates tight coupling: changing the parent's implementation can break all subclasses.

### Invariant 2: Composition Models HAS-A
- Composition means a class HAS another class as a field. Example: `Car` has an `Engine`.
- Composition allows swapping the contained object at runtime via an interface reference (loose coupling).
- "Favour composition over inheritance" means: prefer HAS-A when you need code reuse, reserve IS-A for genuine type hierarchies.

### Invariant 3: Method Resolution in Inheritance
- When a method is called on a subclass object, Java looks for the method in the subclass first, then walks up the inheritance chain.
- A subclass can override a parent method (same signature) to provide specialised behaviour.
- A subclass CANNOT override a `final` method or a `static` method (static methods are hidden, not overridden).

---

## 2. Common Fallacy Patterns (Known Misconceptions)

### `INHERITANCE_IS_CODE_REUSE_ONLY`
- **Description:** Student treats inheritance purely as copy-avoidance, ignoring the IS-A semantic contract.
- **Example flawed claim:** *I use inheritance whenever two classes share methods to avoid rewriting code.*
- **Pedagogical counter:** If Stack extends ArrayList just to reuse add(), a Stack IS NOT an ArrayList. Callers can use get(index) on a Stack, breaking the Stack's LIFO contract. This violates the Liskov Substitution Principle.

### `MULTIPLE_INHERITANCE_VIA_CLASSES`
- **Description:** Student believes Java supports multiple class inheritance.
- **Example flawed claim:** *I can write `class C extends A, B` in Java to inherit from both.*
- **Pedagogical counter:** Java forbids this because of the Diamond Problem: if A and B both define `method()`, which version does C inherit? Java solves this by allowing multiple interface implementation but only single class inheritance.

### `SUPER_CREATES_PARENT_OBJECT`
- **Description:** Student believes calling `super()` creates a separate parent object.
- **Example flawed claim:** *When Dog's constructor calls super(), it creates an Animal object inside the Dog.*
- **Pedagogical counter:** There is only ONE object on the heap. `super()` calls the parent constructor to initialise the parent's portion of THAT SAME object's fields. No separate Animal is created.

---

## 3. Lecture Notes

Inheritance is a mechanism for creating a new class from an existing class. The child class inherits all non-private members of the parent. The key semantic is IS-A: a `Dog` IS an `Animal`, so any function that accepts `Animal` must work correctly when given a `Dog`.

This is where students go wrong: they use inheritance for code reuse without checking the IS-A relationship. The classic bad example is `Stack extends ArrayList`. Yes, Stack reuses ArrayList's methods. But a Stack is NOT an ArrayList — an ArrayList supports random access, which violates Stack's LIFO discipline.

**Composition** is the alternative. Instead of inheriting, a class holds a reference to another class as a field. `Car` doesn't extend `Engine`; it HAS an `Engine`. This is looser coupling: you can swap a `GasEngine` for an `ElectricEngine` at runtime if both implement the `Engine` interface.

The `super` keyword calls the parent class's constructor or method. Crucially, `super()` does NOT create a new parent object. There is only one object in memory — `super()` initialises the parent's fields within that same object.

---

## 4. Lecture Transcript (Excerpt)

> "Here's my test for whether inheritance is right: can you say 'X IS-A Y' and mean it? Dog IS-A Animal — yes. Stack IS-A ArrayList — no, because ArrayList lets you access any index, and a Stack must not. If IS-A fails, use composition. Give Stack a private ArrayList field and expose only push() and pop(). Problem solved, and nobody can break your LIFO contract."

---

## 5. Opening Question

Hey! When would you choose inheritance over composition, and what's the key test to decide between the two?
