
# DORA METRICS
DORA is a set of four critical indicators of software delivery. The DORA metrics, developed by Google’s DevOps Research and Assessment (DORA) group in Google Cloud, focus on evaluating how well a DevOps team delivers software in terms of throughput and stability. By offering measurable and valuable insights into the software delivery performance, teams can drive continuous improvement and improve their overall DevOps performance.

The four DORA metrics are:

* __Deployment frequency__: How many times per day does your team deploy code? High-performing teams have frequent deployments, which indicates a more efficient and responsive delivery process.
* __Change lead time__: This measures how quickly an organization can deploy new code to production. Shorter lead times represent the efficiency of your entire pipeline. For instance, if your code changes move from development to production in 3 days, consider reducing it to 3 hours.
* __Change fail percentage__: What percentage of deployments cause failure in production? Lower rates reflect better deployment processes. This means a team with a 2% failure rate has a better DevOps process compared to one with a 15% rate. Identify areas where processes can be improved to reduce errors and maintain system stability, pay attention to how changes in one area affect other areas, and use software development lifecycle tools to streamline your workflows.
* __Failed deployment recovery time__: How quickly can your team recover from an outage or failed deployment? What is the average time? If you plan to reduce downtime, measuring your time to recovery will help you minimize disruptions and improve operational performance. The faster, the better.

## Benchmarks Metrics for teams

| Performance Level |    Deployment Frequency     |         Lead Time | Change Failure Rate | Mean Time To Recovery (MTTR) |
|:------------------|:---------------------------:|------------------:|--------------------:|-----------------------------:|
| Elite             |          on-demand          |   less than 1 day |                 5 % |                     < 1 hour |
| High              |  once a day to once a week  |   1 day to 1 week |                 10% |                        < day |
| Medium            | once a week to once a month | 1 week to 1 month |                 15% |              1 day to 1 week |
| Low               | once a week to once a month | 1 week to 1 month |                 64% |          1 month to 6 months |

# SPACE METRICS
The SPACE framework acknowledges that developer productivity is multidimensional. SPACE is an acronym for satisfaction, performance, activity, collaboration, and efficiency. It looks beyond technical performance and more into the human factors of operational efficiency.

SPACE highlights the importance of people and recognizes that happy, well-supported teams tend to perform better. While DORA focuses on throughput and stability, SPACE takes a view on engineering productivity, especially team well-being and collaboration.

Coined by some Microsoft researchers, the SPACE metrics are built around these five pillars:

* __Satisfaction and well-being__: This pillar asks the following questions: are your developers happy and healthy? Do they have an appropriate work-life balance? Do you know how they deal with stress and burnout?
* __Performance__: Is the team achieving meaningful outcomes? Identify what performance means for your team and align it with business goals.
* __Activity__: What actions contribute to productivity? What tasks are being completed, and how often? While the activity metric itself doesn’t equate to productivity, tracking it helps understand how time and effort are spent.
* __Collaboration and communication__: Are your development and operations teams working together effectively? Collaboration and effective communication reduce misunderstandings and give room for innovation.
* __Efficiency & flow metric__: How smoothly are processes running? This last metric in the SPACE framework focuses on measuring how quickly and effectively teams complete tasks with minimal effort. 

## DORA metrics vs. SPACE metrics
DORA metrics focus on technical performance and the efficiency of the software delivery process, while SPACE metrics look at the overall performance of the team, including not just technical factors but also human and social factors.

| Category	        |                        DORA Metrics	                        |                                    SPACE Metrics |
|:-----------------|:-----------------------------------------------------------:|-------------------------------------------------:|
| Focus	           | Delivery performance, in terms of throughput and stability	 | Productivity, collaboration, and team well-being |
| Scope	           |                  Team/organizational level                  |             	Individual, team, and system levels |
| Metric type      |                     	Outcome-oriented	                      |  Multifaceted (behavior, outcomes, satisfaction) |
| Primary audience |           	DevOps Engineers, Operations managers            |     	Engineers, HR, project managers, team leads |
