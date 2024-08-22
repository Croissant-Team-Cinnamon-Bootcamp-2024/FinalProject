from datetime import datetime

import requests
from datasets import Dataset
from langchain_groq import ChatGroq
from ragas import evaluate
from ragas.metrics import faithfulness

MODEL = "llama3-70b-8192"


class GenerateRAGAnswer:
    def __init__(
        self,
        query: str,
        course: str,
        context_search_url: str,
        model=MODEL,
    ):
        self.query = query
        self.course = course
        self.context_search_url = context_search_url
        self.model = ChatGroq(model=model, temperature=0)
        self.contexts = None  # To store the retrieved contexts

    def retrieve_contexts(self, top_k=5):
        search_query = {
            "course_name": self.course,
            "text": self.query,
            "top_k": top_k,
        }
        try:
            r = requests.post(url=self.context_search_url, json=search_query)
            response = r.json()

            self.contexts = [
                {"text": text, "metadata": metadata}
                for text, metadata in zip(response['documents'], response['metadatas'])
            ]
            return self.contexts
        except Exception:
            raise

    def gen_prompt(self) -> str:
        # Extract the 'text' field from each context dictionary
        context_texts = [f"{ctx['text']}" for ctx in self.contexts]

        # Join the extracted text with double newlines
        context = "\n\n".join(context_texts)

        prompt_template = (
            """
            You are a teaching assistant.
            Given a set of relevant information from teacher's recording during the lesson """
            """(delimited by <info></info>), please compose an answer to the question of a student.
            Ensure that the answer is accurate, has a friendly tone, and sounds helpful.
            If you cannot answer, ask the student to clarify the question.
            If no context is available in the system, """
            f"""please answer that you can not find the relevant context in the system.
            <info>
            {context}
            </info>
            Question: {self.query}
            Answer: """
        )

        return prompt_template

    def generate_answer(self) -> str:
        before = datetime.now()
        #################################################################################
        # process retrieve or not
        #################################################################################

        self.retrieve_contexts()
        print(f"Retrieve context time: {datetime.now() - before} seconds")
        final_prompt = self.gen_prompt()

        before = datetime.now()
        res = self.model.invoke(final_prompt)
        print(f"LLM return time: {datetime.now() - before} seconds")

        llm_answer = res['content'] if isinstance(res, dict) else res.content

        # Calculate score
        before = datetime.now()
        # faithfulness_score = self.calculate_faithfulness(llm_answer)
        # answer_relevancy_score = self.calculate_answer_relevancy(llm_answer)
        print(f"Eval answer time: {datetime.now() - before} seconds")

        context_list = [
            {"context": ctx["text"], "metadata": ctx["metadata"]}
            for ctx in self.contexts
        ]

        # evidence = (
        #    f"**Retrieved Contexts:**\n{context_str}\n\n"
        #    f"**Faithfulness Score:** {faithfulness_score:.4f}\n"
        #    f"**Answer Relevancy Score:** {answer_relevancy_score:.4f}"
        # )

        evidence = {
            "context_list": context_list,
            # "f_score": faithfulness_score,
            # "ar_score": answer_relevancy_score,
        }

        return llm_answer, evidence

    def calculate_faithfulness(self, generated_answer: str) -> float:
        if not self.contexts:
            raise ValueError(
                "Contexts have not been retrieved. Ensure contexts are retrieved before this method is called."
            )

        model = self.model

        # Prepare the dataset for evaluation
        data_samples = {
            'question': [self.query],
            'answer': [generated_answer],
            'contexts': [[val["text"] for val in self.contexts]],
        }
        dataset = Dataset.from_dict(data_samples)

        # Evaluate faithfulness
        score = evaluate(dataset, metrics=[faithfulness], llm=model)

        # Convert score to pandas DataFrame and get the first score
        score_df = score.to_pandas()
        return score_df['faithfulness'].iloc[0]

    def calculate_answer_relevancy(self, generated_answer: str) -> float:
        if not self.contexts:
            raise ValueError(
                "Contexts have not been retrieved. Ensure contexts are retrieved before this method is called."
            )

        model = self.model

        # Prepare the dataset for evaluation
        data_samples = {
            'question': [self.query],
            'answer': [generated_answer],
            'contexts': [[val["text"] for val in self.contexts]],
        }
        dataset = Dataset.from_dict(data_samples)

        # Evaluate faithfulness
        score = evaluate(dataset, metrics=[faithfulness], llm=model)

        # Convert score to pandas DataFrame and get the first score
        score_df = score.to_pandas()
        return score_df['faithfulness'].iloc[0]


# Example usage
if __name__ == "__main__":
    prompt = "What method do we use if we want to predict house price in an area?"
    course = "cs229_stanford"

    # Create an instance of GenerateRAGAnswer with the query and course
    rag_generator = GenerateRAGAnswer(query=prompt, course=course)

    # Generate and print the answer along with its embedded faithfulness score
    answer = rag_generator.generate_answer()
    print(answer)
