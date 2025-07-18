import json
import asyncio
import time
from typing import Dict, Any, List, Optional
from pathlib import Path

from .context_manager import ContextManager
from .tools import ShellTool, CodeExecutor, XDotTool, FileSystemTool, SecurityError

class CodingAgent:
    """
    Main coding agent that orchestrates tools and manages context
    """
    
    def __init__(self, workspace_dir: str = "/workspace"):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(exist_ok=True)
        
        # Initialize components
        self.context_manager = ContextManager(workspace_dir)
        self.shell_tool = ShellTool(workspace_dir)
        self.code_executor = CodeExecutor(workspace_dir)
        self.xdot_tool = XDotTool(workspace_dir)
        self.filesystem_tool = FileSystemTool(workspace_dir)
        
        # Status tracking
        self.current_task = None
        self.status = "idle"
        self.progress = []
        
        # Add initial context
        self.context_manager.add_context(
            "Agent initialized with tools: shell, code_executor, xdot, filesystem",
            "conversation"
        )
    
    def log_progress(self, message: str, level: str = "info"):
        """Log progress message"""
        timestamp = time.time()
        progress_item = {
            'timestamp': timestamp,
            'level': level,
            'message': message
        }
        self.progress.append(progress_item)
        
        # Add to context
        self.context_manager.add_context(
            f"[{level.upper()}] {message}",
            "conversation"
        )
        
        print(f"[{level.upper()}] {message}")
    
    def execute_task(self, task: str) -> Dict[str, Any]:
        """Execute a high-level task"""
        self.current_task = task
        self.status = "running"
        self.progress = []
        
        self.log_progress(f"Starting task: {task}")
        
        try:
            # Add task to context
            self.context_manager.add_context(f"New task: {task}", "conversation")
            
            # Get relevant context for the task
            relevant_context = self.context_manager.get_relevant_context(task)
            
            self.log_progress(f"Retrieved {len(relevant_context)} relevant context items")
            
            # Parse and execute the task
            result = self._parse_and_execute_task(task, relevant_context)
            
            self.status = "completed"
            self.log_progress("Task completed successfully")
            
            return {
                'status': 'success',
                'result': result,
                'progress': self.progress,
                'context_summary': self.context_manager.get_context_summary()
            }
            
        except Exception as e:
            self.status = "error"
            error_msg = f"Task failed: {str(e)}"
            self.log_progress(error_msg, "error")
            
            return {
                'status': 'error',
                'error': str(e),
                'progress': self.progress,
                'context_summary': self.context_manager.get_context_summary()
            }
    
    def _parse_and_execute_task(self, task: str, context: List) -> Dict[str, Any]:
        """Parse task and execute appropriate actions"""
        task_lower = task.lower()
        
        # Example task parsing (this would be much more sophisticated in a real implementation)
        if "todo app" in task_lower or "todo list" in task_lower:
            return self._create_todo_app(task)
        elif "react" in task_lower and ("app" in task_lower or "application" in task_lower):
            return self._create_react_app(task)
        elif "python" in task_lower and ("script" in task_lower or "program" in task_lower):
            return self._create_python_script(task)
        elif "test" in task_lower:
            return self._run_tests(task)
        else:
            return self._general_task_execution(task)
    
    def _create_todo_app(self, task: str) -> Dict[str, Any]:
        """Create a todo application"""
        self.log_progress("Creating todo app with React")
        
        # Create project structure
        self.filesystem_tool.create_file("package.json", json.dumps({
            "name": "todo-app",
            "version": "1.0.0",
            "scripts": {
                "start": "react-scripts start",
                "build": "react-scripts build",
                "test": "react-scripts test",
                "eject": "react-scripts eject"
            },
            "dependencies": {
                "react": "^18.2.0",
                "react-dom": "^18.2.0",
                "react-scripts": "5.0.1"
            },
            "browserslist": {
                "production": [">0.2%", "not dead", "not op_mini all"],
                "development": ["last 1 chrome version", "last 1 firefox version", "last 1 safari version"]
            }
        }, indent=2))
        
        # Create App.js
        app_code = '''import React, { useState } from 'react';
import './App.css';

function App() {
  const [todos, setTodos] = useState([]);
  const [input, setInput] = useState('');

  const addTodo = () => {
    if (input.trim()) {
      setTodos([...todos, { id: Date.now(), text: input, completed: false }]);
      setInput('');
    }
  };

  const toggleTodo = (id) => {
    setTodos(todos.map(todo => 
      todo.id === id ? { ...todo, completed: !todo.completed } : todo
    ));
  };

  const deleteTodo = (id) => {
    setTodos(todos.filter(todo => todo.id !== id));
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Todo App</h1>
        <div className="todo-input">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && addTodo()}
            placeholder="Add a new todo..."
          />
          <button onClick={addTodo}>Add</button>
        </div>
        <div className="todo-list">
          {todos.map(todo => (
            <div key={todo.id} className={`todo-item ${todo.completed ? 'completed' : ''}`}>
              <span onClick={() => toggleTodo(todo.id)}>{todo.text}</span>
              <button onClick={() => deleteTodo(todo.id)}>Delete</button>
            </div>
          ))}
        </div>
      </header>
    </div>
  );
}

export default App;
'''
        
        self.filesystem_tool.create_file("src/App.js", app_code)
        
        # Create CSS
        css_code = '''.App {
  text-align: center;
}

.App-header {
  background-color: #282c34;
  padding: 20px;
  color: white;
  min-height: 100vh;
}

.todo-input {
  margin: 20px 0;
}

.todo-input input {
  padding: 10px;
  margin-right: 10px;
  border: none;
  border-radius: 4px;
  width: 300px;
}

.todo-input button {
  padding: 10px 20px;
  background-color: #61dafb;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.todo-list {
  max-width: 500px;
  margin: 0 auto;
}

.todo-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px;
  margin: 5px 0;
  background-color: #3a3f47;
  border-radius: 4px;
}

.todo-item span {
  cursor: pointer;
  flex-grow: 1;
  text-align: left;
}

.todo-item.completed span {
  text-decoration: line-through;
  opacity: 0.6;
}

.todo-item button {
  background-color: #ff6b6b;
  color: white;
  border: none;
  padding: 5px 10px;
  border-radius: 4px;
  cursor: pointer;
}
'''
        
        self.filesystem_tool.create_file("src/App.css", css_code)
        
        # Create index.js
        index_code = '''import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
'''
        
        self.filesystem_tool.create_file("src/index.js", index_code)
        
        # Create index.css
        index_css = '''body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
    'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue',
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

code {
  font-family: source-code-pro, Menlo, Monaco, Consolas, 'Courier New',
    monospace;
}
'''
        
        self.filesystem_tool.create_file("src/index.css", index_css)
        
        # Create public/index.html
        html_code = '''<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="theme-color" content="#000000" />
    <meta name="description" content="A simple todo app built with React" />
    <title>Todo App</title>
  </head>
  <body>
    <noscript>You need to enable JavaScript to run this app.</noscript>
    <div id="root"></div>
  </body>
</html>
'''
        
        self.filesystem_tool.create_file("public/index.html", html_code)
        
        # Install dependencies and start
        self.log_progress("Installing dependencies...")
        install_result = self.shell_tool.execute("npm install", timeout=120)
        
        if install_result['success']:
            self.log_progress("Dependencies installed successfully")
            
            # Start the development server
            self.log_progress("Starting development server...")
            self.shell_tool.execute("npm start > /dev/null 2>&1 &")
            
            self.log_progress("Todo app created and started on port 3000")
            
            return {
                'type': 'react_todo_app',
                'files_created': ['package.json', 'src/App.js', 'src/App.css', 'src/index.js', 'src/index.css', 'public/index.html'],
                'url': 'http://localhost:3000',
                'features': ['Add todos', 'Mark as complete', 'Delete todos', 'Responsive design']
            }
        else:
            raise Exception(f"Failed to install dependencies: {install_result['stderr']}")
    
    def _create_react_app(self, task: str) -> Dict[str, Any]:
        """Create a generic React application"""
        self.log_progress("Creating React application")
        
        # Use create-react-app
        result = self.shell_tool.execute("npx create-react-app my-app --yes", timeout=180)
        
        if result['success']:
            self.log_progress("React app created successfully")
            
            # Start the app
            start_result = self.shell_tool.execute("cd my-app && npm start > /dev/null 2>&1 &")
            
            return {
                'type': 'react_app',
                'directory': 'my-app',
                'url': 'http://localhost:3000',
                'status': 'running'
            }
        else:
            raise Exception(f"Failed to create React app: {result['stderr']}")
    
    def _create_python_script(self, task: str) -> Dict[str, Any]:
        """Create a Python script based on task description"""
        self.log_progress("Creating Python script")
        
        # Simple example - create a hello world script
        script_content = '''#!/usr/bin/env python3
"""
Simple Python script generated by coding agent
"""

def main():
    print("Hello from the coding agent!")
    print("This script was generated based on your task:")
    print(f"{task}")

if __name__ == "__main__":
    main()
'''
        
        self.filesystem_tool.create_file("script.py", script_content)
        
        # Make executable and run
        self.shell_tool.execute("chmod +x script.py")
        result = self.code_executor.execute_python(script_content)
        
        self.log_progress("Python script created and executed")
        
        return {
            'type': 'python_script',
            'file': 'script.py',
            'execution_result': result
        }
    
    def _run_tests(self, task: str) -> Dict[str, Any]:
        """Run tests in the current project"""
        self.log_progress("Running tests")
        
        # Try different test runners
        test_commands = [
            "npm test -- --watchAll=false",
            "python -m pytest",
            "python -m unittest discover"
        ]
        
        results = []
        for cmd in test_commands:
            result = self.shell_tool.execute(cmd, timeout=60)
            results.append({
                'command': cmd,
                'result': result
            })
            
            if result['success']:
                self.log_progress(f"Tests passed with: {cmd}")
                break
        
        return {
            'type': 'test_execution',
            'results': results
        }
    
    def _general_task_execution(self, task: str) -> Dict[str, Any]:
        """Handle general tasks"""
        self.log_progress("Executing general task")
        
        # List current directory
        dir_list = self.filesystem_tool.list_directory(".")
        
        # Create a simple report
        report = f"""
Task: {task}

Current workspace contents:
{json.dumps(dir_list, indent=2)}

Context summary:
{json.dumps(self.context_manager.get_context_summary(), indent=2)}
"""
        
        self.filesystem_tool.create_file("task_report.txt", report)
        
        return {
            'type': 'general_task',
            'report_file': 'task_report.txt',
            'workspace_contents': dir_list
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get current agent status"""
        return {
            'status': self.status,
            'current_task': self.current_task,
            'progress': self.progress[-10:],  # Last 10 items
            'context_summary': self.context_manager.get_context_summary(),
            'workspace_dir': str(self.workspace_dir)
        }

async def main():
    """Main agent loop for testing"""
    agent = CodingAgent()
    
    print("Coding Agent Started")
    print("Workspace:", agent.workspace_dir)
    print("Status:", agent.get_status())
    
    # Keep running
    while True:
        await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())