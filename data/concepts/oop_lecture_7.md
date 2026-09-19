# Lecture 7: SOLID Principles and Design Basics

**Course:** CS3301 Object-Oriented Analysis and Design  
**Department:** Computer Science and Engineering, CEG Anna University

---

## 1. Ground Truth Invariants

### Invariant 1: Single Responsibility Principle (SRP)
- A class should have ONE reason to change — it should do one thing and do it well.
- A "God class" that handles UI, database, and business logic violates SRP because a UI change forces modifying a class that also handles data.
- SRP does NOT mean a class has only one method. It means all methods in the class serve the same cohesive purpose.

### Invariant 2: Open/Closed Principle (OCP)
- Software entities should be OPEN for extension but CLOSED for modification.
- You should be able to add new behaviour (e.g., a new shape type) by adding new code (a new class), NOT by modifying existing working code.
- This is achieved through abstraction: depending on interfaces/abstract classes rather than concrete implementations.

### Invariant 3: Dependency Inversion Principle (DIP)
- High-level modules should NOT depend on low-level modules. Both should depend on abstractions.
- Example: A `NotificationService` should depend on a `MessageSender` interface, not directly on `EmailSender`. This allows swapping to `SMSSender` without changing `NotificationService`.
- DIP is NOT dependency injection. DIP is the principle (depend on abstractions). Dependency injection is one technique to achieve it.

---

## 2. Common Fallacy Patterns (Known Misconceptions)

### `SRP_MEANS_ONE_METHOD`
- **Description:** Student interprets SRP as "one class, one method."
- **Example flawed claim:** *SRP says each class should have only one method.*
- **Pedagogical counter:** A `UserValidator` class might have `validateEmail()`, `validatePassword()`, and `validateAge()` — three methods, but one responsibility: validation. SRP is about cohesion of purpose, not counting methods.

### `OCP_MEANS_NEVER_MODIFY`
- **Description:** Student believes existing code must literally never be touched.
- **Example flawed claim:** *Once a class is written, I can never change it — that's OCP.*
- **Pedagogical counter:** OCP means you should DESIGN code so that adding new features doesn't require modifying existing code. Bug fixes and refactoring are still allowed. The principle is about architectural planning, not a coding prohibition.

### `DIP_IS_DEPENDENCY_INJECTION`
- **Description:** Student conflates the Dependency Inversion Principle with the Dependency Injection pattern.
- **Example flawed claim:** *DIP means using a framework like Spring to inject dependencies.*
- **Pedagogical counter:** DIP says "depend on abstractions, not concretions" — it's a design principle. Dependency injection is one implementation technique. You can follow DIP without any framework by simply coding to interfaces. And you can use dependency injection without following DIP if you inject concrete classes.

---

## 3. Lecture Notes

The SOLID principles are five guidelines for writing maintainable, extensible OOP code.

**Single Responsibility (SRP)**: Each class has one job. A `ReportGenerator` generates reports — it doesn't also send emails and log to databases. If your class has methods that serve different stakeholders (UI team vs DB team), split it.

**Open/Closed (OCP)**: Design so that adding new functionality means writing new classes, not editing existing ones. Use abstract classes or interfaces as extension points. When a new `PaymentMethod` is needed, create a `CryptoPayment` class implementing the `PaymentMethod` interface — don't add `if (type == "crypto")` to existing code.

**Dependency Inversion (DIP)**: High-level policy should not depend on low-level details. If `OrderService` directly creates `MySQLDatabase`, it can never work with PostgreSQL without code changes. Instead, `OrderService` depends on a `Database` interface, and the concrete implementation is provided externally.

The "God Class" anti-pattern is the opposite of SRP: one massive class that handles everything. It's fragile (any change can break unrelated features) and untestable (you can't test email without also loading the database code).

---

## 4. Lecture Transcript (Excerpt)

> "I see students write one class with 2000 lines — the User class that validates input, queries the database, sends emails, generates PDFs, and makes coffee. That's a God class. When the email provider changes, you're editing the same class that handles database queries. That's dangerous. SRP says split it: `UserValidator`, `UserRepository`, `UserNotifier`. Each has one reason to change. And please — SRP doesn't mean one method per class. It means one responsibility. A validator can have ten validation methods; they all serve the same purpose."

---

## 5. Opening Question

Hey! Can you explain what the Single Responsibility Principle means — and is it about limiting the number of methods in a class?
