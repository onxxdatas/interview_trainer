"""Curated question bank.

Each topic maps to a list of concepts, and each concept to a list of
questions with metadata. This is the "structured" half of the hybrid
approach described in the spec — Gemini generates variations and
follow-ups on top of this, but the core bank is fixed and reviewable.

Difficulty: 1 basic, 2 intermediate, 3 advanced, 4 internals, 5 interview trap.
"""

from __future__ import annotations

SEED_DATA: dict[str, dict] = {
    "python-fundamentals": {
        "name": "Python Fundamentals",
        "concepts": {
            "mutability": {
                "name": "Mutability",
                "questions": [
                    dict(difficulty=1, qtype="conceptual",
                         body="Explain the difference between mutable and immutable objects in Python, with examples of each.",
                         expected_points=["mutable objects can change in place", "immutable objects cannot",
                                           "examples: list/dict/set mutable, tuple/str/int immutable"]),
                    dict(difficulty=2, qtype="code_prediction",
                         body="Predict the values of a, b, c and explain why.",
                         code_snippet="a = [1, 2, 3]\nb = a\nc = a.copy()\nb.append(4)\nprint(a, b, c)",
                         expected_points=["b is the same object as a, so a and b both show the append",
                                           "c is a separate shallow copy so c is unaffected"]),
                    dict(difficulty=3, qtype="debugging",
                         body="This function is buggy. Why does calling it twice give unexpected accumulating results, and how would you fix it?",
                         code_snippet="def add_item(item, bucket=[]):\n    bucket.append(item)\n    return bucket",
                         expected_points=["mutable default argument is created once at function definition time",
                                           "fix: use bucket=None and create a new list inside the function"]),
                ],
            },
            "is-vs-eq": {
                "name": "is vs ==",
                "questions": [
                    dict(difficulty=1, qtype="conceptual",
                         body="What is the difference between `is` and `==` in Python?",
                         expected_points=["== compares value equality via __eq__",
                                           "is compares object identity (same object in memory)",
                                           "is should not be used for normal value comparison"]),
                    dict(difficulty=4, qtype="follow_up",
                         body="What does id() have to do with is?",
                         expected_points=["id() returns a unique identifier for an object's identity during its lifetime",
                                           "in CPython this is typically the memory address",
                                           "`a is b` is roughly equivalent to `id(a) == id(b)`"]),
                ],
            },
            "scope-legb": {
                "name": "Scope and LEGB",
                "questions": [
                    dict(difficulty=1, qtype="conceptual",
                         body="What is LEGB in Python and how does name resolution work?",
                         expected_points=["Local, Enclosing, Global, Built-in", "resolution order from innermost to outermost",
                                           "closures capture the enclosing scope"]),
                    dict(difficulty=3, qtype="output_prediction",
                         body="What does this print, and why?",
                         code_snippet="def outer():\n    x = 1\n    def inner():\n        x += 1\n        return x\n    return inner()\n\nouter()",
                         expected_points=["UnboundLocalError because x += 1 makes x local to inner()",
                                           "assignment anywhere in a function makes that name local unless declared nonlocal"]),
                ],
            },
            "decorators": {
                "name": "Decorators",
                "questions": [
                    dict(difficulty=2, qtype="conceptual",
                         body="Explain what a decorator is and write a simple decorator that logs a function's execution time.",
                         expected_points=["a decorator wraps a function to extend its behavior without modifying it",
                                           "uses functools.wraps to preserve metadata", "returns a wrapper function"]),
                    dict(difficulty=3, qtype="implementation",
                         body="Implement a decorator `@retry(times=3)` that retries a function on exception.",
                         expected_points=["decorator factory pattern (decorator taking arguments)",
                                           "loop with try/except and re-raise after exhausting attempts"]),
                ],
            },
            "closures": {
                "name": "Closures",
                "questions": [
                    dict(difficulty=2, qtype="conceptual",
                         body="What is a closure in Python? Give an example where a closure is useful.",
                         expected_points=["a function that captures variables from its enclosing scope",
                                           "the enclosing scope persists after the outer function returns"]),
                ],
            },
        },
    },
    "oop": {
        "name": "Object-Oriented Python",
        "concepts": {
            "mro": {
                "name": "MRO and super()",
                "questions": [
                    dict(difficulty=3, qtype="conceptual",
                         body="What is MRO (Method Resolution Order) and how does Python compute it?",
                         expected_points=["order in which base classes are searched for a method",
                                           "computed with the C3 linearization algorithm",
                                           "super() follows the MRO, not just the immediate parent"]),
                    dict(difficulty=4, qtype="output_prediction",
                         body="Given this diamond inheritance, what is the MRO of D and what does D().who() print?",
                         code_snippet="class A:\n    def who(self): return 'A'\nclass B(A):\n    def who(self): return 'B'\nclass C(A):\n    def who(self): return 'C'\nclass D(B, C):\n    pass\n\nprint(D().who())",
                         expected_points=["MRO: D, B, C, A, object", "D().who() prints 'B' because B is first in MRO"]),
                ],
            },
            "descriptors": {
                "name": "Descriptors",
                "questions": [
                    dict(difficulty=4, qtype="conceptual",
                         body="What is a descriptor in Python? How do properties relate to descriptors?",
                         expected_points=["an object implementing __get__/__set__/__delete__",
                                           "property is implemented as a descriptor",
                                           "descriptors let you customize attribute access at the class level"]),
                ],
            },
            "dunder": {
                "name": "Dunder methods",
                "questions": [
                    dict(difficulty=2, qtype="conceptual",
                         body="What is the difference between __repr__ and __str__, and when is each used?",
                         expected_points=["__repr__ is for developers/debugging, should be unambiguous",
                                           "__str__ is for end users, falls back to __repr__ if not defined"]),
                ],
            },
        },
    },
    "memory-management": {
        "name": "Python Memory Management",
        "concepts": {
            "reference-counting": {
                "name": "Reference counting & GC",
                "questions": [
                    dict(difficulty=3, qtype="conceptual",
                         body="How does CPython manage memory? Explain reference counting and when the garbage collector is needed.",
                         expected_points=["CPython primarily uses reference counting",
                                           "objects are freed immediately when refcount hits zero",
                                           "the cyclic garbage collector handles reference cycles that refcounting can't"]),
                    dict(difficulty=4, qtype="debugging",
                         body="This creates a reference cycle. Explain why it isn't cleaned up immediately and how it eventually gets collected.",
                         code_snippet="class Node:\n    def __init__(self):\n        self.parent = None\n        self.child = None\n\na = Node()\nb = Node()\na.child = b\nb.parent = a",
                         expected_points=["a and b reference each other, refcount never reaches 0 via refcounting alone",
                                           "the generational cyclic GC detects and collects unreachable cycles"]),
                ],
            },
        },
    },
    "cpython-internals": {
        "name": "CPython Internals",
        "concepts": {
            "bytecode": {
                "name": "Bytecode and frames",
                "questions": [
                    dict(difficulty=4, qtype="conceptual",
                         body="What is Python bytecode, and what role does a frame object play during execution?",
                         expected_points=["source is compiled to bytecode executed by the CPython VM",
                                           "a frame holds local variables, the bytecode being executed, and the instruction pointer",
                                           "each function call creates a new frame"]),
                ],
            },
        },
    },
    "concurrency": {
        "name": "Concurrency",
        "concepts": {
            "gil": {
                "name": "GIL",
                "questions": [
                    dict(difficulty=3, qtype="conceptual",
                         body="What is the GIL and how does it affect multi-threaded CPU-bound vs I/O-bound Python programs?",
                         expected_points=["Global Interpreter Lock allows only one thread to execute Python bytecode at a time",
                                           "CPU-bound threads don't get true parallelism, use multiprocessing instead",
                                           "I/O-bound threads release the GIL while waiting, so threading still helps"]),
                ],
            },
            "asyncio": {
                "name": "asyncio & event loop",
                "questions": [
                    dict(difficulty=3, qtype="conceptual",
                         body="Explain how the asyncio event loop works and what makes a coroutine different from a regular function.",
                         expected_points=["single-threaded event loop schedules coroutines cooperatively",
                                           "coroutines yield control at await points instead of blocking",
                                           "good for I/O-bound, not CPU-bound work"]),
                ],
            },
        },
    },
    "dsa": {
        "name": "Algorithms and Data Structures",
        "concepts": {
            "big-o": {
                "name": "Big-O complexity",
                "questions": [
                    dict(difficulty=2, qtype="big_o",
                         body="What is the time and space complexity of this function, and why?",
                         code_snippet="def has_duplicate(nums):\n    seen = set()\n    for n in nums:\n        if n in seen:\n            return True\n        seen.add(n)\n    return False",
                         expected_points=["time O(n) because set lookups are average O(1)",
                                           "space O(n) for the set in the worst case"]),
                ],
            },
            "lru-cache": {
                "name": "LRU Cache",
                "questions": [
                    dict(difficulty=4, qtype="implementation",
                         body="Implement an LRU cache with get(key) and put(key, value) in O(1) time.",
                         expected_points=["hash map + doubly linked list (or OrderedDict)",
                                           "O(1) get and put by moving accessed nodes to the front"]),
                ],
            },
            "binary-search": {
                "name": "Binary search",
                "questions": [
                    dict(difficulty=2, qtype="implementation",
                         body="Implement binary search on a sorted list and state its time complexity.",
                         expected_points=["O(log n)", "two pointers narrowing the search range"]),
                ],
            },
        },
    },
    "testing": {
        "name": "Testing",
        "concepts": {
            "pytest-fixtures": {
                "name": "pytest fixtures & mocking",
                "questions": [
                    dict(difficulty=2, qtype="conceptual",
                         body="What are pytest fixtures for, and how would you mock an external API call in a unit test?",
                         expected_points=["fixtures provide reusable setup/teardown for tests",
                                           "unittest.mock.patch or monkeypatch to replace the real call",
                                           "keeps tests isolated from network/external state"]),
                ],
            },
        },
    },
    "backend": {
        "name": "Backend / Django / DRF / PostgreSQL",
        "concepts": {
            "db-indexes": {
                "name": "Database indexes",
                "questions": [
                    dict(difficulty=3, qtype="architecture",
                         body="What is a database index, and what are the trade-offs of adding one to a frequently-written table?",
                         expected_points=["index speeds up reads/lookups on indexed columns",
                                           "slows down writes because the index must be updated too",
                                           "extra storage cost"]),
                ],
            },
            "drf-serializers": {
                "name": "DRF serializers & views",
                "questions": [
                    dict(difficulty=2, qtype="architecture",
                         body="In Django REST Framework, what is the responsibility of a serializer versus a view/viewset?",
                         expected_points=["serializer: validation + converting between Python objects and JSON",
                                           "view: handles the HTTP request/response cycle and permissions/routing"]),
                ],
            },
        },
    },
}
