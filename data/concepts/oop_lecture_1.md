# Lecture 1: Classes and Objects

**Course:** CS3301 Object-Oriented Analysis and Design  
**Department:** Computer Science and Engineering, CEG Anna University

---

## 1. Ground Truth Invariants

### Invariant 1: Class vs Object
- A class is a blueprint (template) that defines fields and methods. It occupies no runtime memory for its instances until instantiated.
- An object is a specific instance of a class, allocated on the heap at runtime with its own copy of instance fields.
- Multiple objects of the same class each have independent field values but share the same method code.

### Invariant 2: Constructor Behaviour
- A constructor is called exactly once per object creation (via `new` in Java/C++). It initialises the object's fields.
- If no constructor is defined, the compiler provides a default no-argument constructor. But if ANY constructor is explicitly defined, the default is NOT generated — you must define it yourself if you still need it.
- A constructor does NOT return a value (not even void). It is NOT a regular method.

### Invariant 3: The `this` / `self` Reference
- Inside an instance method, `this` (Java/C++) or `self` (Python) refers to the current object the method was called on.
- `this` is an implicit parameter passed by the runtime — it is NOT a global variable.
- Static methods do NOT have a `this` reference because they belong to the class, not to any instance.

---

## 2. Common Fallacy Patterns (Known Misconceptions)

### `CLASS_IS_AN_OBJECT`
- **Description:** Student believes a class and an object are the same thing.
- **Example flawed claim:** *When I write `class Dog`, that creates a Dog in memory.*
- **Pedagogical counter:** Writing `class Dog` defines what a Dog looks like. No Dog exists in memory until you write `new Dog()`. How many Dogs exist after `class Dog` alone? Zero.

### `CONSTRUCTOR_IS_A_METHOD`
- **Description:** Student treats the constructor as a regular method that can be called multiple times or has a return type.
- **Example flawed claim:** *I can call the constructor again to reset my object's fields.*
- **Pedagogical counter:** Calling `new Dog()` creates a NEW Dog — it does not reset the existing one. If constructors were regular methods, what would `Dog d = d.Dog()` return? The language forbids this syntax because constructors are not methods.

### `STATIC_MEANS_CONSTANT`
- **Description:** Student conflates static members with constants.
- **Example flawed claim:** *A static variable cannot be changed because static means fixed.*
- **Pedagogical counter:** `static int count = 0; count++;` compiles and runs. Static means shared across all instances, not immutable. `final` (Java) or `const` (C++) makes something immutable.

---

## 3. Lecture Notes

Classes and objects form the foundation of object-oriented programming. A **class** is a user-defined type that bundles data (fields/attributes) and behaviour (methods) into a single unit. Think of it as a cookie cutter — the cutter defines the shape, but no cookie exists until you press it into dough.

An **object** is a runtime instance of a class. When you write `Dog d = new Dog();`, the `new` operator allocates heap memory for one Dog's fields and calls the constructor to initialise them. The variable `d` holds a reference (an address) to that heap memory — it does not hold the Dog itself.

**Constructors** are special initialisation routines. They share the class name, have no return type, and run exactly once during `new`. A common mistake is assuming the compiler always provides a default constructor — it only does so when you define zero constructors yourself.

The **`this` keyword** inside a method refers to the object on which the method was invoked. It disambiguates when a parameter name shadows a field name: `this.name = name;`. Static methods belong to the class, not any object, so `this` is unavailable inside them.

---

## 4. Lecture Transcript (Excerpt)

> "Right, so today we start with the most basic question — what is a class? A class is NOT an object. I repeat, a class by itself creates nothing in memory. It's a template. When I write `class Car { int speed; }`, no Car exists yet. It's only when I write `Car c = new Car()` that the JVM allocates memory on the heap for that Car's speed field. One class, many objects. Each object has its own speed value. The constructor runs once during `new` — you cannot call it again on the same object. And please remember: if you define even one constructor with parameters, the compiler stops generating the default one. This bites people in exams every year."

---

## 5. Opening Question

Hey! What's your understanding of how a class differs from an object, and what exactly happens when you write `new Dog()` in Java?
