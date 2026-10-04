"""
Intake Triage Assistant — main application window.

Flow: login -> paste a request -> Claude drafts category + response ->
staff reviews and edits -> explicit "Approve & Save" click is the only
thing that writes a final record. Nothing the AI drafts is ever saved
or treated as final without that click.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
from dotenv import load_dotenv

import storage
import config
import claude_client

load_dotenv()


class LoginWindow(tk.Tk):
    def __init__(self, on_success):
        super().__init__()
        self.title("Intake Triage Assistant — Login")
        self.geometry("320x180")
        self.on_success = on_success

        tk.Label(self, text="Username").pack(pady=(20, 0))
        self.username_entry = tk.Entry(self)
        self.username_entry.pack()

        tk.Label(self, text="Password").pack(pady=(10, 0))
        self.password_entry = tk.Entry(self, show="*")
        self.password_entry.pack()
        self.password_entry.bind("<Return>", lambda e: self.attempt_login())

        tk.Button(self, text="Log In", command=self.attempt_login).pack(pady=15)

    def attempt_login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        conn = storage.get_connection()
        user = storage.verify_user(conn, username, password)
        if user is None:
            storage.log_action(conn, username or "(blank)", "failed_login")
            conn.close()
            messagebox.showerror("Login failed", "Incorrect username or password.")
            return
        storage.log_action(conn, username, "login")
        conn.close()
        self.destroy()
        self.on_success(dict(user))


class MainWindow(tk.Tk):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.title(f"Intake Triage Assistant — logged in as {user['username']} ({user['role']})")
        self.geometry("700x600")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        self.new_request_tab = NewRequestTab(notebook, self.user)
        notebook.add(self.new_request_tab, text="New Request")

        self.history_tab = HistoryTab(notebook)
        notebook.add(self.history_tab, text="History")

        if user["role"] == "admin":
            self.audit_tab = AuditTab(notebook)
            notebook.add(self.audit_tab, text="Audit Log (admin)")

        notebook.bind("<<NotebookTabChanged>>", lambda e: self.refresh_all())

    def refresh_all(self):
        self.history_tab.refresh()
        if self.user["role"] == "admin":
            self.audit_tab.refresh()


class NewRequestTab(tk.Frame):
    def __init__(self, parent, user):
        super().__init__(parent)
        self.user = user
        self.pending_id = None

        tk.Label(self, text="Incoming request:", font=("", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 0))
        self.request_box = tk.Text(self, height=6, wrap="word")
        self.request_box.pack(fill="x", padx=10)

        tk.Button(self, text="Get AI Suggestion", command=self.get_suggestion).pack(pady=8)

        tk.Label(self, text="Suggested category (edit if needed):").pack(anchor="w", padx=10)
        self.category_var = tk.StringVar()
        self.category_dropdown = ttk.Combobox(
            self, textvariable=self.category_var, values=config.load_categories()
        )
        self.category_dropdown.pack(fill="x", padx=10)

        tk.Label(self, text="Suggested response (edit before approving):").pack(anchor="w", padx=10, pady=(10, 0))
        self.response_box = tk.Text(self, height=6, wrap="word")
        self.response_box.pack(fill="x", padx=10)

        tk.Label(
            self,
            text="Nothing is saved until you click Approve & Save.",
            fg="#555555",
        ).pack(pady=(8, 0))

        tk.Button(
            self, text="Approve & Save", bg="#2e7d32", fg="white", command=self.approve
        ).pack(pady=10)

    def get_suggestion(self):
        text = self.request_box.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("Empty request", "Paste or type a request first.")
            return
        try:
            suggestion = claude_client.get_suggestion(text)
        except claude_client.SuggestionError as e:
            messagebox.showerror(
                "AI suggestion unavailable",
                f"{e}\n\nYou can still fill in the category and response manually.",
            )
            return

        self.category_var.set(suggestion["category"])
        self.response_box.delete("1.0", "end")
        self.response_box.insert("1.0", suggestion["response"])

        conn = storage.get_connection()
        self.pending_id = storage.save_pending_request(
            conn, text, suggestion["category"], suggestion["response"]
        )
        storage.log_action(conn, self.user["username"], "ai_suggestion_generated", f"request_id={self.pending_id}")
        conn.close()

    def approve(self):
        final_category = self.category_var.get().strip()
        final_response = self.response_box.get("1.0", "end").strip()
        request_text = self.request_box.get("1.0", "end").strip()

        if not final_category or not final_response or not request_text:
            messagebox.showwarning("Incomplete", "Request, category, and response all need to be filled in.")
            return

        conn = storage.get_connection()
        if self.pending_id is None:
            # human filled everything manually without calling the AI first
            self.pending_id = storage.save_pending_request(conn, request_text, None, None)
        storage.approve_request(conn, self.pending_id, final_category, final_response, self.user["username"])
        conn.close()

        messagebox.showinfo("Saved", "Request approved and saved.")
        self.request_box.delete("1.0", "end")
        self.response_box.delete("1.0", "end")
        self.category_var.set("")
        self.pending_id = None


class HistoryTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        columns = ("id", "approved_at", "final_category", "approved_by")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        for col in columns:
            self.tree.heading(col, text=col)
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        self.refresh()

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        conn = storage.get_connection()
        for r in storage.fetch_history(conn):
            self.tree.insert("", "end", values=(r["id"], r["approved_at"], r["final_category"], r["approved_by"]))
        conn.close()


class AuditTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        columns = ("timestamp", "username", "action", "detail")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        for col in columns:
            self.tree.heading(col, text=col)
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        self.refresh()

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        conn = storage.get_connection()
        for r in storage.fetch_audit_log(conn):
            self.tree.insert("", "end", values=(r["timestamp"], r["username"], r["action"], r["detail"]))
        conn.close()


def launch_main(user):
    MainWindow(user).mainloop()


if __name__ == "__main__":
    storage.init_db()
    LoginWindow(on_success=launch_main).mainloop()
