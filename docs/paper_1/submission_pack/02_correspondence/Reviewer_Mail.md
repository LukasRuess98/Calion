Ms. Ref. No.: APEN-D-26-15734
Title: Topology Resolution Dominates Dispatch Accuracy in District Heating

Networks with Industrial Demands: A Five-Level MILP Comparison
Applied Energy

Dear Mr. Lukas Ruess,

The reviewers/editors have commented on your above paper. They indicated that it is not acceptable for publication in its present form.

However, if you feel that you can suitably address the reviewers' comments (included below or the attachments in your account), I invite you to revise and resubmit your manuscript.

Please contact the journal mailbox "appliedenergy@elsevier.com" if in case of any issues or queries about the missing attachments or reviewer comments.

To view your reviewer feedback, please log in as an author at https://www.editorialmanager.com/apen/ and navigate to your manuscript in the "" Submissions Needing Revision "" folder under the Author Main Menu.  
 
When revising your manuscript, please consider all issues mentioned in the reviewers' comments carefully. Please note that your revised submission may need to be re-reviewed.  

To submit your revision, please do the following:
1. Go to: https://www.editorialmanager.com/apen/
2. Enter your login details
3. Click [Author Login]
This takes you to the Author Main Menu.
4. Click [Submissions Needing Revision]


Please proceed to the following link to update your personal classifications and keywords, if necessary:
Update Personal Classifications and Keywords

The revised version of your submission is due by Aug 29, 2026. Please contact editor-in-chief, if more time is needed.

Include interactive data visualizations in your publication and let your readers interact and engage more closely with your research. Follow the instructions here: https://www.elsevier.com/authors/author-services/data-visualization to find out about available data visualization options and how to include them with your article.

Research Elements (optional)
This journal encourages you to share research objects - including your raw data, methods, protocols, software, hardware and more – which support your original research article in a Research Elements journal. Research Elements are open access, multidisciplinary, peer-reviewed journals which make the objects associated with your research more discoverable, trustworthy and promote replicability and reproducibility. As open access journals, there may be an Article Publishing Charge if your paper is accepted for publication. Find out more about the Research Elements journals at https://www.elsevier.com/authors/tools-and-resources/research-elements-journals?dgcid=ec_em_research_elements_email.


I look forward to receiving your revised manuscript.

Yours sincerely,

Prof.Wenqiang Sun
Editor-in-chief
Applied Energy



Reviewers' and Editors' comments:




Reviewer #1: The study uses controlled pairwise comparisons to separate the effects of topology resolution, physical fidelity, and mathematical linearisation. It applies the framework to a 12 MW industrial heating network and 36 synthetic network configurations, comprising 184 optimisation instances. The main result is that resolving network topology and thermal losses has a substantially greater influence on calculated dispatch costs than adding detailed hydraulic and thermal physics. The paper is relevant to the journal and my concerns are as follows:

1. The title and main conclusion state that topology resolution "dominates" dispatch accuracy. However, this result is demonstrated for radial networks with fixed capacities, centrally located generation, prescribed heating curves, unidirectional flow, and fixed or precomputed supply-temperature-dependent parameters. Ring networks, distributed generation, variable-temperature operation, bidirectional flows, and investment decisions are explicitly excluded. This incurrs that the central conclusion is broader than the demonstrated scope.

2. The paper primarily measures differences in objective values and dispatch outcomes between model formulations. A larger model is treated as a more accurate reference, but the post-upgrade optimal dispatch cannot be directly compared with measured operation. Consequently, the analysis demonstrates model-result sensitivity to fidelity choices, rather than dispatch accuracy in the strict empirical sense. This distinction matters because a 13% difference between L1 and L3 does not prove that L3 is 13% more accurate unless L3 outcomes are independently validated. The authors should either revise the terminology or provide a clearer definition of accuracy and its reference benchmark.

3. The L3+-L3NL comparison simultaneously changes the mathematical treatment of nonlinear terms and activates transport delay. The reported difference of up to 0.5% therefore represents a combined effect rather than an isolated linearisation error. The manuscript itself acknowledges that the two effects cannot be separated without an intermediate formulation. This weakens one of the paper's claimed methodological contributions.

4. The pipe model is calibrated and validated using data collected before the installation of the heat pump, electrode boiler, and thermal storage. The operation of these new assets is evaluated through plausibility checks rather than post-upgrade measurements. This two-stage procedure is reasonable given data limitations, but it does not fully validate the dispatch interactions that drive the study's cost conclusions.

5. Supply and return temperatures follow prescribed heating curves, heat-pump COP values are precomputed, pipe thermal losses are largely parameterised, and sub-hourly dynamics are excluded. Under these assumptions, temperature optimisation, dynamic thermal inertia, and hydraulic constraints have limited ability to alter dispatch decisions.

6. The L2 model aggregates the detailed network into seven zones while matching the total UL product of the detailed network. This is a reasonable controlled design, but alternative clustering methods could yield different spatial routing and loss distributions even when total annual losses are preserved.

7. The analysis uses hourly resolution and deterministic annual dispatch. It excludes forecast uncertainty, reserve requirements, sub-hourly industrial demand changes, and operational disturbances. These factors may affect the value of transport delay, thermal storage, heat-pump flexibility, and network constraints.





Reviewer #2: The manuscript presents a five-level comparison of district-heating network models and evaluates their effects on operational cost, emissions, and computational performance. The combination of an industrial case study and synthetic networks is potentially useful. However, I have substantial concerns regarding the manuscript's novelty. Most formulations and physical components are established methods, and the main contribution appears to be their comparative application. More importantly, the current experiments do not convincingly support the central claim that topology resolution dominates dispatch accuracy. The manuscript therefore requires substantial revision before its contribution can be assessed as sufficiently significant.
1. The methodological novelty is currently limited. The five model levels mainly combine existing representations of network topology, heat losses, pressure drops, temperature propagation, and transport delay. The authors should clearly distinguish the genuinely new methodological contribution from a structured comparison of established models. The Introduction and contribution statements should also explain what new knowledge is obtained beyond previous model-fidelity studies.
2. The claimed dominance of topology is not adequately demonstrated. The transition from L1 to L2 introduces both spatial network representation and pipe heat losses. Consequently, the resulting cost and emission differences cannot be attributed specifically to topology resolution. A copperplate model incorporating calibrated aggregate heat losses should be added to separate the effects of topology and thermal losses. Otherwise, the title and principal conclusions should be moderated.
3. The reported linearization error of less than 0.5% is not rigorously established. L3+ and L3NL differ not only in linearization but also in their treatment of transport delay. Moreover, the reported solver gaps are comparable to the observed objective differences. Intermediate models, optimality-bound intervals, or comparisons against a validated nonlinear reference are needed before drawing a general conclusion regarding linearization accuracy.
4. The hydraulic and thermal validation should be strengthened. The relatively large flow errors, strongly calibrated pipe-loss multipliers, and exceptionally low pumping-energy estimate raise questions about physical fidelity. The authors should clarify the modelling of supply and return networks, substations, valves, pressure requirements, and pump characteristics, and provide additional out-of-sample validation where possible.
5. The general applicability of the proposed model-selection rules is uncertain. Only 36 of the 81 synthetic configurations were retained, and the model-level definitions are not fully consistent between the industrial and synthetic studies. The authors should justify the filtering procedure, adopt a consistent taxonomy, and use a more balanced statistical analysis. Otherwise, the proposed network-length and complexity thresholds should be presented as case-specific observations rather than general guidelines.


Senior Editor:
In addition to the comments from the above reviewers, please also pay attention to the following aspects while improving the quality of your manuscript.
- Avoid lumping references, such as [1-3]. Please cite just the most relevant and necessary references. Please follow the comment throughout the whole paper.
- The Abstract should be merged into one paragraph.
- Do not use subheadings in Conclusion section.
- The structure of the manuscript should be modified, please refer to recently published papers in the journal.



******************************************


Note: After the paper is accepted to production, we do not allow any authorship changes in your article since the editor would like to approve any changes to the authorship before acceptance of papers in EM.



NOTE: Upon submitting your revised manuscript, please upload the source files for your article. For additional details regarding acceptable file formats, please refer to the Guide for Authors at: http://www.elsevier.com/journals/applied-energy/0306-2619/guide-for-authors

When submitting your revised paper, we ask that you include the following items:

Manuscript and Figure Source Files (mandatory)

We cannot accommodate PDF manuscript files for production purposes. We also ask that when submitting your revision you follow the journal formatting guidelines. Figures and tables may be embedded within the source file for the submission as long as they are of sufficient resolution for Production.For any figure that cannot be embedded within the source file (such as *.PSD Photoshop files), the original figure needs to be uploaded separately.

Highlights (mandatory)

Highlights consist of a short collection of bullet points that convey the core findings of the article and should be submitted in a separate file in the online submission system. Please use 'Highlights' in the file name and include 3 to 5 bullet points (maximum 85 characters, including spaces, per bullet point). See the following website for more information
http://www.elsevier.com/highlights

Graphical Abstract (optional)

Graphical Abstracts should summarize the contents of the article in a concise, pictorial form designed to capture the attention of a wide readership online. Refer to the following website for more information: http://www.elsevier.com/graphicalabstracts

Please note that the editorial process varies considerably from journal to journal. To view a sample editorial process, please click here:
http://help.elsevier.com/app/answers/detail/p/7923/a_id/160

For further assistance, please visit our customer support site at http://help.elsevier.com/app/answers/list/p/7923. Here you can search for solutions on a range of topics, find answers to frequently asked questions and learn more about EM via interactive tutorials. You will also find our 24/7 support contact details should you need any further assistance from one of our customer support representatives.

At Elsevier, we want to help all our authors to stay safe when publishing. Please be aware of fraudulent messages requesting money in return for the publication of your paper. If you are publishing open access with Elsevier, bear in mind that we will never request payment before the paper has been accepted. We have prepared some guidelines (https://www.elsevier.com/connect/authors-update/seven-top-tips-on-stopping-apc-scams ) that you may find helpful, including a short video on Identifying fake acceptance letters (https://www.youtube.com/watch?v=o5l8thD9XtE ). Please remember that you can contact Elsevier s Researcher Support team (https://service.elsevier.com/app/home/supporthub/publishing/) at any time if you have questions about your manuscript, and you can log into Editorial Manager to check the status of your manuscript (https://service.elsevier.com/app/answers/detail/a_id/29155/c/10530/supporthub/publishing/kw/status/).

#AU_APEN#

To ensure this email reaches the intended recipient, please do not delete the above code
 
 

________________________________________
In compliance with data protection regulations, you may request that we remove your personal registration details at any time. (Remove my information/details). Please contact the publication office if you have any questions.  
