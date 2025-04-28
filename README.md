# NeuroForge

**NeuroForge** is a web-based platform that bridges the gap between evolutionary computation and neural network research, providing an accessible environment for optimizing neural networks through genetic algorithms.

The platform enables researchers, students, and developers to evolve weights for custom PyTorch models without requiring deep expertise in evolutionary computation. By combining a user-friendly interface with powerful computational capabilities, NeuroForge democratizes access to advanced optimization techniques while maintaining flexibility for experienced practitioners to configure parameters, define custom model architectures, and implement specialized evaluation functions.

![Screenshot 2025-04-23 181453](https://github.com/user-attachments/assets/591c02a0-d7aa-4e91-b885-fbd9581ad091)


---

## 🛠️ System Architecture

NeuroForge’s architecture combines modern web technologies with sophisticated AI components to create a comprehensive research environment.

- **Frontend**: Built with Next.js and React, offering interactive visualizations of evolutionary processes using Recharts.
- **Backend**: Python-based FastAPI server managing computational workload via Celery task queues.
- **Core Components**:
  - **Genetic Algorithm Engine** for neural network weight optimization.
  - **Retrieval-Augmented Generation (RAG) AI Advisor** powered by **LlamaIndex**, providing contextual answers grounded in research literature.
  - **AI-Driven Analysis** using **Google’s Gemini** to interpret evolutionary results.
- **Deployment**: Fully containerized with **Docker** for performance scalability and simplified deployment.

---

## ⚡ Key Features

- 📦 **Upload Custom PyTorch Models**: Easily integrate your own neural network architectures.
- ⚙️ **Genetic Algorithm Configuration**: Fine-tune parameters through a flexible, user-friendly interface.
- 📈 **Real-Time Monitoring**: Interactive plots track fitness and diversity metrics throughout the evolution process.
- 💾 **Model Download**: Retrieve optimized models upon completion of the evolutionary run.
- 🤖 **AI Advisor**: Query a knowledge base of AI research papers and receive contextual, citation-backed answers.
- 🔍 **Gemini Analysis**: Automated interpretation of evolutionary results, providing insights beyond raw metrics.

---

## 🚀 Why NeuroForge?

NeuroForge distinguishes itself through its holistic approach to neural network research:

- Seamless integration of **experimentation**, **analysis**, and **knowledge acquisition**.
- **No deep evolutionary computation expertise required** — ideal for researchers, students, and developers.
- Combines **evolutionary computation**, **large language models**, and **interactive visualization** in a unified platform.
- Designed for **flexibility** for experts and **simplicity** for beginners.

---

## 📚 Technologies Used

- **Frontend**: Next.js, React, Recharts
- **Backend**: FastAPI, Celery
- **AI Components**: LlamaIndex, Google's Gemini
- **Containerization**: Docker
- **Frameworks**: PyTorch for neural network modeling

---

## 🎯 Goals

- Democratize access to evolutionary neural network optimization.
- Foster research and education in machine learning and artificial intelligence.
- Provide an extensible, modular environment for future AI advancements.

---
