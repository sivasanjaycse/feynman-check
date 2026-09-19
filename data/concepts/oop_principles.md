# Concept Invariants: Object-Oriented Programming (OOP) Core Principles

**Course:** CS3301 Object-Oriented Analysis and Design  
**Department:** Computer Science and Engineering, CEG Anna University

---

## 1. Ground Truth Invariants

### Invariant 1: Inheritance vs. Composition
- Inheritance (`extends`) models an IS-A relationship: a subclass IS a specialised form of the parent.
- Composition models a HAS-A relationship: a class HAS another class as a field.
- Key distinction: Inheritance creates tight coupling (changing the parent affects all subclasses). Composition allows swapping the contained object via an interface (loose coupling).

### Invariant 2: Polymorphism — Dynamic Dispatch
- Method overriding achieves RUNTIME polymorphism. When a Parent reference holds a Child object and the child overrides a method, calling that method dispatches to the CHILD implementation at runtime — not the parent.
- Method overloading is COMPILE-TIME (static) polymorphism: the compiler selects the version based on argument types at compile time.
- A cast to the parent type does NOT change which overriding method is called.

### Invariant 3: Encapsulation and Access Control
- `private` members are accessible ONLY within the declaring class. Subclasses cannot access them directly (they exist in the object's memory but are invisible to subclass code).
- `protected` members are accessible within the class, its subclasses, and classes in the same package.

---

## 2. Common Fallacy Patterns (Known Misconceptions)

### `INHERITANCE_IS_CODE_REUSE_ONLY`
- **Description:** Student treats inheritance purely as copy-avoidance, ignoring the IS-A semantic contract.
- **Example flawed claim:** *I use inheritance whenever two classes share methods to avoid rewriting code.*
- **Pedagogical counter:** If Stack extends ArrayList just to reuse add(), a Stack IS NOT an ArrayList. Callers can use get(index) on a Stack, breaking the Stack's LIFO contract. This violates the Liskov Substitution Principle and causes bugs.

### `OVERLOADING_EQUALS_OVERRIDING`
- **Description:** Student conflates method overloading (compile-time) with method overriding (runtime).
- **Example flawed claim:** *When I define add(int) and add(double) in the same class, that is overriding.*
- **Pedagogical counter:** With overloading, the compiler picks the version at compile time based on the declared type of the reference. Overriding dispatches at runtime based on the actual object type. These are fundamentally different mechanisms with different timing.

### `PRIVATE_MEMBERS_INHERITED`
- **Description:** Student believes private fields are accessible in subclasses.
- **Example flawed claim:** *Since Dog extends Animal, Dog can access Animal's private fields directly.*
- **Pedagogical counter:** If private members were accessible in subclasses, the private keyword would provide no encapsulation. Any internal refactoring of the parent would silently break the child's direct field access.

### `POLYMORPHISM_ONLY_WORKS_WITH_CASTING`
- **Description:** Student believes you must cast to a child type to invoke the overriding child method.
- **Example flawed claim:** *To call Dog's speak() method, I must cast Animal a to Dog first.*
- **Pedagogical counter:** If Animal a = new Dog() and Dog overrides speak(), calling a.speak() dispatches to Dog.speak() WITHOUT any cast. Casting is only needed to access methods that exist ONLY in Dog and are not overriding anything in Animal.
