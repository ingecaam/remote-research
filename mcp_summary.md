# Architecture Overview — Model Context Protocol (MCP)

> Source: https://modelcontextprotocol.io/docs/concepts/architecture

---

## Introduction

This overview of the Model Context Protocol (MCP) discusses its scope and core concepts, and provides an example demonstrating each core concept. Because MCP SDKs abstract away many concerns, most developers will likely find the **data layer protocol** section to be the most useful. It discusses how MCP servers can provide context to an AI application.

---

## Scope

The Model Context Protocol includes the following projects:

- **MCP Specification**: A specification of MCP that outlines the implementation requirements for clients and servers.
- **MCP SDKs**: SDKs for different programming languages that implement MCP.
- **MCP Development Tools**: Tools for developing MCP servers and clients, including the MCP Inspector.
- **MCP Reference Server Implementations**: Reference implementations of MCP servers.

> MCP focuses solely on the protocol for context exchange — it does not dictate how AI applications use LLMs or manage the provided context.

---

## Concepts of MCP

### Participants

MCP follows a **client-server architecture** where an **MCP host** (an AI application like Claude Code or Claude Desktop) establishes connections to one or more **MCP servers**. The MCP host does this by creating one MCP client per MCP server.

| Participant  | Role |
|---|---|
| **MCP Host** | The AI application that coordinates and manages one or multiple MCP clients |
| **MCP Client** | A component that maintains a connection to an MCP server and obtains context for the host to use |
| **MCP Server** | A program that provides context to MCP clients |

- **Local MCP servers** use STDIO transport and typically serve a single MCP client.
- **Remote MCP servers** use Streamable HTTP transport and can serve many MCP clients.

---

### Layers

MCP consists of two layers:

1. **Data Layer**: Defines the JSON-RPC based protocol for client-server communication, including lifecycle management and core primitives (tools, resources, prompts, notifications).
2. **Transport Layer**: Defines the communication mechanisms and channels (connection establishment, message framing, authorization).

> Conceptually, the data layer is the **inner** layer and the transport layer is the **outer** layer.

---

#### Data Layer

Implements a **JSON-RPC 2.0** based exchange protocol. Includes:

- **Lifecycle management**: Handles connection initialization, capability negotiation, and termination.
- **Server features**: Tools (AI actions), Resources (context data), Prompts (interaction templates).
- **Client features**: Sampling (LLM completions), Elicitation (user input), Logging.
- **Utility features**: Notifications (real-time updates), Progress tracking (long-running operations).

#### Transport Layer

Manages communication channels and authentication. MCP supports two transport mechanisms:

| Transport | Description |
|---|---|
| **Stdio transport** | Uses standard input/output streams for direct local process communication. Optimal performance, no network overhead. |
| **Streamable HTTP transport** | Uses HTTP POST for client-to-server messages with optional Server-Sent Events (SSE) for streaming. Supports bearer tokens, API keys, custom headers. MCP recommends OAuth for authentication. |

---

### Data Layer Protocol

#### Lifecycle Management

MCP requires lifecycle management to negotiate capabilities that both client and server support. The connection starts with a capability negotiation handshake.

#### Primitives

MCP **primitives** define what clients and servers can offer each other.

**Server-side primitives:**

| Primitive | Description |
|---|---|
| **Tools** | Executable functions AI applications can invoke (e.g., file operations, API calls, DB queries) |
| **Resources** | Data sources providing contextual information (e.g., file contents, DB records, API responses) |
| **Prompts** | Reusable templates for structuring LLM interactions (e.g., system prompts, few-shot examples) |

Each primitive type supports:
- **Discovery**: `*/list` methods
- **Retrieval**: `*/get` methods
- **Execution** (tools only): `tools/call`

**Client-side primitives:**

| Primitive | Description |
|---|---|
| **Sampling** | Allows servers to request LLM completions via `sampling/createMessage` |
| **Elicitation** | Allows servers to request additional user input via `elicitation/create` |
| **Logging** | Enables servers to send log messages to clients |

**Cross-cutting utility primitives:**

| Primitive | Description |
|---|---|
| **Tasks** *(Experimental)* | Durable execution wrappers for deferred result retrieval and status tracking (e.g., batch processing, multi-step operations) |

#### Notifications

The protocol supports **real-time notifications** using JSON-RPC 2.0 notification messages (no response expected). For example, when a server's tool list changes, it sends a `notifications/tools/list_changed` event to connected clients.

---

## Example: Data Layer Walkthrough

### Step 1 — Initialization (Lifecycle Management)

The client sends an `initialize` request to negotiate capabilities:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-06-18",
    "capabilities": { "elicitation": {} },
    "clientInfo": { "name": "example-client", "version": "1.0.0" }
  }
}
```

Key purposes:
1. **Protocol Version Negotiation**: Ensures compatible versions.
2. **Capability Discovery**: Declares supported features (tools, resources, prompts, notifications).
3. **Identity Exchange**: Provides identification for debugging.

After successful initialization, the client sends:

```json
{ "jsonrpc": "2.0", "method": "notifications/initialized" }
```

---

### Step 2 — Tool Discovery (Primitives)

The client sends a `tools/list` request to discover available tools:

```json
{ "jsonrpc": "2.0", "id": 2, "method": "tools/list" }
```

Each tool in the response includes:
- `name`: Unique identifier
- `title`: Human-readable display name
- `description`: Explanation of the tool's purpose
- `inputSchema`: JSON Schema defining expected parameters

---

### Step 3 — Tool Execution (Primitives)

The client invokes a tool using `tools/call`:

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "weather_current",
    "arguments": {
      "location": "San Francisco",
      "units": "imperial"
    }
  }
}
```

The response includes a `content` array of typed content objects (e.g., `"type": "text"`), supporting rich multi-format responses.

---

### Step 4 — Real-time Updates (Notifications)

When the server's tool list changes, it sends a notification (no `id` field, no response expected):

```json
{ "jsonrpc": "2.0", "method": "notifications/tools/list_changed" }
```

The client then refreshes its tool list:

```json
{ "jsonrpc": "2.0", "id": 4, "method": "tools/list" }
```

**Why notifications matter:**
- **Dynamic environments**: Tools may come and go based on server state.
- **Efficiency**: No need to poll for changes.
- **Consistency**: Clients always have accurate capability information.
- **Real-time collaboration**: AI applications adapt to changing contexts.

---

*Content fetched from: https://modelcontextprotocol.io/docs/concepts/architecture*
