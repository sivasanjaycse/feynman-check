# Lecture 2: Encapsulation and Access Modifiers

**Course:** CS3301 Object-Oriented Analysis and Design  
**Department:** Computer Science and Engineering, CEG Anna University

---

## 1. Ground Truth Invariants

### Invariant 1: Encapsulation Principle
- Encapsulation means bundling data (fields) and the methods that operate on that data into a single class, AND restricting direct access to the internal data.
- The purpose is to protect object invariants: external code cannot put the object into an illegal state if it can only interact through controlled methods (getters/setters with validation).

### Invariant 2: Access Modifier Semantics (Java)
- `private`: Accessible ONLY within the declaring class. Not visible to subclasses, not visible to same-package classes.
- `protected`: Accessible within the declaring class, its subclasses (even in different packages), and other classes in the same package.
- `public`: Accessible from anywhere.
- Default (package-private): Accessible within the same package only. Subclasses in other packages CANNOT access it.

### Invariant 3: Getters/Setters Are Not Automatic Encapsulation
- Simply generating getters and setters for every field is NOT meaningful encapsulation. If `setAge(int age)` accepts any integer without validation, the field might as well be public.
- True encapsulation enforces constraints: `setAge(int age) { if (age < 0) throw ...; this.age = age; }`.

---

## 2. Common Fallacy Patterns (Known Misconceptions)

### `PRIVATE_MEMBERS_INHERITED`
- **Description:** Student believes private fields of a parent class are directly accessible in the subclass.
- **Example flawed claim:** *Since Dog extends Animal, Dog can access Animal's private fields directly.*
- **Pedagogical counter:** If private members were accessible in subclasses, the private keyword would provide no encapsulation. Any internal refactoring of the parent would silently break the child's direct field access. The fields exist in the child object's memory, but the child's code cannot name them.

### `ENCAPSULATION_IS_JUST_HIDING`
- **Description:** Student reduces encapsulation to "making fields private" without understanding the purpose.
- **Example flawed claim:** *Encapsulation means making all variables private. That's it.*
- **Pedagogical counter:** If you make a field private but add a public setter with no validation, anyone can still set it to an invalid value. What did you gain? The point is controlled access with invariant enforcement, not just syntactic hiding.

### `DEFAULT_ACCESS_EQUALS_PRIVATE`
- **Description:** Student believes omitting an access modifier makes a member private.
- **Example flawed claim:** *If I don't write any modifier, the field is private by default.*
- **Pedagogical counter:** In Java, no modifier means package-private — every class in the same package can access it. Try it: create two classes in the same package and access each other's default fields. It compiles. Private would not.

---

## 3. Lecture Notes

Encapsulation is often called the first pillar of OOP. It combines two ideas: **bundling** (data + methods in one class) and **information hiding** (restricting who can touch the data).

Access modifiers in Java enforce visibility at compile time. `private` is the tightest: only code inside the same class can read or write the field. `protected` opens access to subclasses and same-package classes. `public` opens access to everyone. The default (no modifier) is package-private, which many students confuse with private.

A critical subtlety: private fields ARE inherited in the sense that they exist in the subclass object's memory layout. But the subclass code cannot refer to them by name. The child must use the parent's public or protected methods to access those fields.

Getters and setters are tools for encapsulation, but only when they add value. A setter that blindly assigns `this.x = x` without any validation is just a verbose public field. Real encapsulation means the setter checks constraints, logs changes, or triggers side effects that maintain the object's consistency.

---

## 4. Lecture Transcript (Excerpt)

> "Let me ask you this: if I make `balance` private in BankAccount and then write `public void setBalance(double b) { this.balance = b; }` — is the balance actually protected? No! Anyone can call `setBalance(-1000)` and corrupt the account. Encapsulation is not about the keyword `private` — it's about the contract. The setter should reject negative values. That's the whole point."

---

## 5. Opening Question

Hey! Can you explain what encapsulation really means in OOP and why simply making a field private isn't enough by itself?
