# Simple Order System

The Web Store calls the Order Service when a customer places or views an order. The Order Service
uses the Orders Database to save and retrieve orders. The Commerce Team owns both services.

```mermaid
flowchart LR
    Customer[Customer] --> Web[Web Store]
    Web --> Orders[Order Service]
    Orders --> Database[(Orders Database)]
    Team[Commerce Team] -. owns .-> Web
    Team -. owns .-> Orders
```
