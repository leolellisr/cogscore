# CogScore - An Online Evaluation Playground For Cognitive Architectures With Developmental Robotics.

## CONAIM

The CONAIM model (Conscious Attention-Based Integrated Model) (Simões, 2015) draws inspiration from the attentional architecture proposed by Colombini (2014), with a specific focus on replacing the attentional controller. This model aims to endow an attention-based agent with awareness and the ability to compute over the saliency map, resulting in a significant reduction in the dimensionality of the model's input space. The CONAIM model consists of two main systems: an attentional system and a cognitive system.

The attentional system, as proposed by Simões (2015), builds upon the selection for perception model introduced by Colombini (2014). This architecture incorporates various elements from related works and is capable of handling multiple sensory systems, employing multiple processes for feature extraction, decision-making, and learning support.

The cognitive system, also presented by Simões (2015), encompasses memory blocks such as semantic, episodic, procedural, and working memory, as well as performance and individuality modules, which include internal states and body schema. The working memory receives information from the attentional system, specifically the saliency map and sensory memory, and provides information for motivation, emotions, decision-making, performance, and other cognitive processes. The exchange of information between semantic, episodic, and procedural memories and working memory occurs bidirectionally, facilitating a comprehensive information flow.

Additionally, a set of processes operate in parallel and synchronize with the modules to perform actions on the elements of the cognitive system. The CONAIM model operates under the paradigm that any function or process within the cognitive system can request information from any other module and/or modify the agent's internal states at any given time. Consequently, the flow of information through the decision-making module is not obligatory.

