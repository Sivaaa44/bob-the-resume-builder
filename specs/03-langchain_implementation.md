# Change in Implementation Logic

## Resume condensation
- Only the Summary / Bio and the project points should be changes and the education and intern experiences shouldnt be altered
- if there is a possibility to reframe the point of the intern experiences to that of the keywords that are expected from the JD, its ok to modify it
- Even if the point is not relevant to the JD, leave it untouched.
- most of the resume should change the same and the lower important points shouldnt be removed or shortened that makes the entire resume disappear

## JD Parsing
- while parsing JD and matching keywords have like a value between 0 to 1 on how much the JD matches with my resume.
- split constraints into 3 types, Hard Constraints, Soft Constraints, and None
- Hard contstraints are if the role has significantly more years of experience required than what I have
- Soft constraints are if the role is a bit different from my experience, domains etc
- if hardconstraint, pause the execution there itself and ask for human intervention to confirm the continuation or not.

make sure the Base Resume predominantly same and the adjustments should mostly be just replacing the keywords and prioritizing the skills from the JD to that of i already have in resume

Hence rework the condensation logics and the overall execution