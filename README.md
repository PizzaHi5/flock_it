# Flock It

Flock It is a multi-agent trading system that uses LLM-powered agents to analyze market conditions and execute trades based on various trading strategies. The system employs a base agent that coordinates multiple specialized strategy agents, each implementing different trading approaches.

## Features

### Agent Architecture

🤖 Base Strategy Agent with configurable LLM model (default: Claude 3.5 Sonnet)

🔄 Multiple specialized trading strategies:
- Momentum Trading
- Mean Reversion
- Breakout Detection
- Algorithmic Trading
- News Event Trading
- Swing Trading
- Trend Following

📊 Dynamic strategy activation based on market conditions

💡 Intelligent parameter optimization and risk management

**Design Flowchart**
```mermaid
flowchart TB
    subgraph Strategy Manager
        BA[Base Agent<br>Claude 3.5 Sonnet] --> SM[Strategy Manager]
        SM --> |Activates| AS[Active Strategies]
    end
    
    subgraph Trading Strategies
        AS --> |May Activate| MO[Momentum<br>Trading] 
        AS --> |May Activate| MR[Mean<br>Reversion]
        AS --> |May Activate| BR[Breakout<br>Detection]
        AS --> |May Activate| AL[Algorithmic<br>Trading]
        AS --> |May Activate| NE[News Event<br>Trading]
        AS --> |May Activate| SW[Swing<br>Trading]
        AS --> |May Activate| TR[Trend<br>Following]
    end

    subgraph Agent Analysis
        subgraph "Per Agent Data Processing"
            API[Alchemy API]
            NWS[News Data]
            TA[Technical<br>Analysis]
        end

        MO --> |Uses| API & NWS & TA
        MR --> |Uses| API & NWS & TA
        BR --> |Uses| API & NWS & TA
        AL --> |Uses| API & NWS & TA
        NE --> |Uses| API & NWS & TA
        SW --> |Uses| API & NWS & TA
        TR --> |Uses| API & NWS & TA
    end
    
    subgraph Signal Aggregation
        MO & MR & BR & AL & NE & SW & TR --> |Feed Analysis| MC[Market<br>Conditions]
        MC --> |Generates| TS[Trading<br>Signals]
        TS --> |Feeds back to| SM
    end
    
    subgraph Execution
        SM --> |Coordinates| TD[Trade<br>Decisions]
        TD --> |Executes| TR1[Trades on<br>Uniswap V2/V3]
    end
```