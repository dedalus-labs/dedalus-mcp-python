## Technical Governance

The MCP project adopts a hierarchical structure, similar to Python, PyTorch and other open source projects:

* A community of **contributors** who file issues, make pull requests, and contribute to the project.
* A small set of **maintainers** drive components within the MCP project, such as SDKs, documentation, and others.
* Contributors and maintainers are overseen by **core maintainers**, who drive the overall project direction.
* The core maintainers have two **lead core maintainers** who are the catch-all decision makers.
* Maintainers, core maintainers, and lead core maintainers form the **MCP steering group**.

All maintainers are expected to have a strong bias towards MCP's design philosophy. Membership in the technical governance process is for individuals, not companies. That is, there are no seats reserved for specific companies, and membership is associated with the person rather than the company employing that person. This ensures that maintainers act in the best interests of the protocol itself and the open source community.

### Channels

Technical Governance is facilitated through a shared [Discord server](/community/communication#discord) of all **maintainers, core maintainers** and **lead maintainers**. Each maintainer group can choose additional communication channels, but all decisions and their supporting discussions must be recorded and made transparently available on the Discord server.

### Maintainers

Maintainers are responsible for [Working or Interest Groups](/community/working-interest-groups) within the MCP project. These generally are independent repositories such as language-specific SDKs, but can also extend to subdirectories of a repository, such as the MCP documentation. Maintainers may adopt their own rules and procedures for making decisions. Maintainers are expected to make decisions for their respective projects independently, but can defer or escalate to the core maintainers when needed.

Maintainers are responsible for the:

* Thoughtful and productive engagement with community contributors,
* Maintaining and improving their respective area of the MCP project,
* Supporting documentation, roadmaps and other adjacent parts of the MCP project,
* Present ideas from community to core.

Maintainers are encouraged to propose additional maintainers when needed. Maintainers can only be appointed and removed by core maintainers or lead core maintainers at any time and without reason.

Maintainers have write and/or admin access to their respective repositories.

### Core Maintainers

The core maintainers are expected to have a deep understanding of the Model Context Protocol and its specification. Their responsibilities include:

* Designing, reviewing and steering the evolution of the MCP specification, as well as all other parts of the MCP project, such as documentation,
* Articulating a cohesive long-term vision for the project,
* Mediating and resolving contentious issues with fairness and transparency, seeking consensus where possible while making decisive choices when necessary,
* Appoint or remove maintainers,
* Stewardship of the MCP project in the best interest of MCP.

The core maintainers as a group have the power to veto any decisions made by maintainers by majority vote. The core maintainers have power to resolve disputes as they see fit. The core maintainers should publicly articulate their decision-making. The core group is responsible for adopting their own procedures for making decisions.

Core maintainers generally have write and admin access to all MCP repositories, but should use the same contribution (usually pull-requests) mechanism as outside contributors. Exceptions can be made based on security considerations.

### Lead Maintainers (BDFL)

MCP has two lead maintainers: Justin Spahr-Summers and David Soria Parra. Lead Maintainers can veto any decision by core maintainers or maintainers. This model is also commonly known as Benevolent Dictator for Life (BDFL) in the open source community. The Lead Maintainers should publicly articulate their decision-making and give clear reasoning for their decisions. Lead maintainers are part of the core maintainer group.

The Lead Maintainers are responsible for confirming or removing core maintainers.

Lead Maintainers are administrators on all infrastructure for the MCP project where possible. This includes but is not restricted to all communication channels, GitHub organizations and repositories.

### Decision Process

The core maintainer group meets every two weeks to discuss and vote on proposals, as well as discuss any topics needed. The shared Discord server can be used to discuss and vote on smaller proposals if needed.

The lead maintainer, core maintainer, and maintainer group should attempt to meet in person every three to six months.
