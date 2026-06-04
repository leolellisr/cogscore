
// File: org/cst/cogscore/modules/motivation/MotivationTestRunner.java
package org.cst.cogscore.modules.motivation;

import org.cst.cogscore.modules.motivation.MotivationActionSet.Category;
import org.cst.cogscore.modules.motivation.MotivationActionSet.FunctionalType;
import org.cst.cogscore.modules.motivation.MotivationData.ActionEvent;
import org.cst.cogscore.modules.motivation.MotivationData.Phase;

import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.io.PrintWriter;
import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

public class MotivationTestRunner {

    public static final int EXP1_PERSISTENCE = 1;
    public static final int EXP2_DEPRIVATION_SATIATION = 2;
    public static final int EXP3_GOAL_SUBSTITUTION = 3;
    public static final int EXP4_LATENT_LEARNING = 4;
    public static final int EXP5_OUTCOME_DEVALUATION = 5;

    public static final class Config {
        public File outDir = new File("motivation_out");
        public String filePrefix = "motivation";

        public int maxObjects = 8;

        public Config setOutDir(File outDir) {
            this.outDir = outDir;
            return this;
        }

        public Config setFilePrefix(String filePrefix) {
            this.filePrefix = filePrefix;
            return this;
        }

        public Config setMaxObjects(int maxObjects) {
            this.maxObjects = maxObjects;
            return this;
        }
    }

    private final int motivationExperimentId;
    private final Config config;

    public MotivationTestRunner(int motivationExperimentId, Config config) {
        validateExperimentId(motivationExperimentId);
        this.motivationExperimentId = motivationExperimentId;
        this.config = config == null ? new Config() : config;

        if (this.config.outDir != null && !this.config.outDir.exists()) {
            this.config.outDir.mkdirs();
        }
    }

    public MotivationEvaluationReport.TrialResult evaluate(MotivationData.TrialTrace trace) {
        if (trace == null || trace.lastContext == null) {
            throw new IllegalArgumentException("Motivation trial trace is null or incomplete");
        }

        switch (motivationExperimentId) {
            case EXP1_PERSISTENCE:
                return evaluatePersistence(trace);
            case EXP2_DEPRIVATION_SATIATION:
                return evaluateDeprivationSatiation(trace);
            case EXP3_GOAL_SUBSTITUTION:
                return evaluateGoalSubstitution(trace);
            case EXP4_LATENT_LEARNING:
                return evaluateLatentLearning(trace);
            case EXP5_OUTCOME_DEVALUATION:
                return evaluateOutcomeDevaluation(trace);
            default:
                throw new IllegalStateException("Unsupported motivation experiment id: " + motivationExperimentId);
        }
    }

    public MotivationEvaluationReport.Summary summarize(
            String architectureName,
            int episode,
            boolean aborted,
            List<MotivationEvaluationReport.TrialResult> results
    ) {
        MotivationEvaluationReport.Summary s = new MotivationEvaluationReport.Summary();

        s.motivationExperimentId = motivationExperimentId;
        s.experimentId = experimentName(motivationExperimentId);
        s.architectureName = blankToDefault(architectureName, "unknown");
        s.episode = episode;
        s.aborted = aborted;

        if (results != null) {
            s.trials.addAll(results);
        }

        s.totalTrials = s.trials.size();

        s.meanPersistenceDurationCycles = meanField(s.trials, "persistenceDurationCycles");
        s.meanPersistenceSelectivity = meanField(s.trials, "persistenceSelectivity");

        s.resourceChoiceProbability = meanIntField(s.trials, "resourceChoice");
        s.noveltyChoiceProbability = meanIntField(s.trials, "noveltyChoice");
        s.controlChoiceProbability = meanIntField(s.trials, "controlChoice");

        s.resourceModulationIndex =
                choiceProbabilityByConditionAndRole(s.trials, "resource_deprived", "resource")
                        - choiceProbabilityByConditionAndRole(s.trials, "resource_satiated", "resource");

        s.noveltyModulationIndex =
                choiceProbabilityByConditionAndRole(s.trials, "novel", "curiosity")
                        - choiceProbabilityByConditionAndRole(s.trials, "familiar", "curiosity");

        s.substitutionSuccessRate = meanIntField(s.trials, "substitutionSuccess");
        s.meanPerseveration = meanField(s.trials, "perseveration");
        s.meanDetourEfficiency = meanField(s.trials, "detourEfficiency");

        s.meanInspectionCoverage = meanField(s.trials, "inspectionCoverage");
        s.meanManipulationCoverage = meanField(s.trials, "manipulationCoverage");
        s.firstAttemptAccuracyRate = meanIntField(s.trials, "firstAttemptAccuracy");
        s.meanFirstInteractionEfficiency = meanField(s.trials, "firstInteractionEfficiency");

        s.latentLearningGainEfficiency =
                meanEfficiencyByCondition(s.trials, "prior_exploration")
                        - meanEfficiencyByCondition(s.trials, "no_prior_exploration");

        s.latentLearningGainLatency =
                meanGoalInteractionLatencyByCondition(s.trials, "no_prior_exploration")
                        - meanGoalInteractionLatencyByCondition(s.trials, "prior_exploration");

        s.meanDevaluationSensitivity = meanField(s.trials, "devaluationSensitivity");
        s.meanResponseSuppression = meanField(s.trials, "responseSuppression");

        s.meanMotorActionCount = meanIntField(s.trials, "motorActionCount");
        s.meanVirtualActionCount = meanIntField(s.trials, "virtualActionCount");
        s.meanAttentionalActionCount = meanIntField(s.trials, "attentionalActionCount");

        s.omissionRate = meanBooleanOmission(s.trials);
        s.behavioralMotivationScore = computeBehavioralMotivationScore(s);

        return s;
    }

    public void writeEpisodeFiles(MotivationEvaluationReport.Summary summary) throws IOException {
        if (summary == null) {
            return;
        }

        if (config.outDir == null) {
            config.outDir = new File("motivation_out");
        }

        if (!config.outDir.exists() && !config.outDir.mkdirs()) {
            throw new IOException("Could not create output directory: " + config.outDir.getAbsolutePath());
        }

        writePerTrialCsv(summary);
        writeSummaryCsv(summary);
    }

    private MotivationEvaluationReport.TrialResult evaluatePersistence(MotivationData.TrialTrace trace) {
        MotivationEvaluationReport.TrialResult r = buildBaseResult(trace);

        long firstPersistenceCycle = Long.MAX_VALUE;
        long lastPersistenceCycle = Long.MIN_VALUE;
        int targetEvents = 0;
        int controlEvents = 0;

        for (ActionEvent e : trace.actions) {
            if (e.phase != Phase.PERSISTENCE) {
                continue;
            }

            if (e.functionalType == FunctionalType.LOOK
                    || e.functionalType == FunctionalType.INTERACT) {
                firstPersistenceCycle = Math.min(firstPersistenceCycle, e.cycle);
                lastPersistenceCycle = Math.max(lastPersistenceCycle, e.cycle);
            }

            if (e.objectIndex == trace.lastContext.targetObject) {
                targetEvents++;
            }

            if (e.objectIndex == trace.lastContext.controlObject) {
                controlEvents++;
            }
        }

        if (lastPersistenceCycle >= firstPersistenceCycle) {
            r.persistenceDurationCycles = (double) (lastPersistenceCycle - firstPersistenceCycle + 1L);
        } else {
            r.persistenceDurationCycles = 0.0;
        }

        r.persistenceSelectivity =
                ((double) targetEvents) / ((double) targetEvents + (double) controlEvents + 1e-9);

        return r;
    }

    private MotivationEvaluationReport.TrialResult evaluateDeprivationSatiation(MotivationData.TrialTrace trace) {
        MotivationEvaluationReport.TrialResult r = buildBaseResult(trace);

        ActionEvent firstInteraction = trace.firstInteraction();

        if (firstInteraction != null) {
            String role = lower(firstInteraction.objectRole);

            if ("resource".equals(role)) {
                r.resourceChoice = 1;
            } else if ("curiosity".equals(role) || "novelty".equals(role)) {
                r.noveltyChoice = 1;
            } else if ("control".equals(role)) {
                r.controlChoice = 1;
            }
        }

        return r;
    }

    private MotivationEvaluationReport.TrialResult evaluateGoalSubstitution(MotivationData.TrialTrace trace) {
        MotivationEvaluationReport.TrialResult r = buildBaseResult(trace);

        int blockedEvents = 0;
        int alternativeEvents = 0;

        for (ActionEvent e : trace.actions) {
            if (e.phase != Phase.BLOCKED_TEST) {
                continue;
            }

            if (e.objectIndex == trace.lastContext.targetObject) {
                blockedEvents++;
            }

            if (e.objectIndex == trace.lastContext.alternativeObject) {
                alternativeEvents++;
            }
        }

        ActionEvent firstInteraction = firstInteractionInPhase(trace, Phase.BLOCKED_TEST);

        if (firstInteraction != null
                && firstInteraction.objectIndex == trace.lastContext.alternativeObject) {
            r.substitutionSuccess = 1;
        } else {
            r.substitutionSuccess = 0;
        }

        r.perseveration =
                ((double) blockedEvents) / ((double) blockedEvents + (double) alternativeEvents + 1e-9);

        if (firstInteraction != null && firstInteraction.objectIndex == trace.lastContext.alternativeObject) {
            int actionsBeforeSuccess = countEffectiveActionsUntilObjectInPhase(
                    trace,
                    trace.lastContext.alternativeObject,
                    Phase.BLOCKED_TEST
            );

            r.detourEfficiency = 1.0 / Math.max(1, actionsBeforeSuccess);
        } else {
            r.detourEfficiency = 0.0;
        }

        return r;
    }

    private MotivationEvaluationReport.TrialResult evaluateLatentLearning(MotivationData.TrialTrace trace) {
        MotivationEvaluationReport.TrialResult r = buildBaseResult(trace);

        int objectCount = Math.max(1, trace.lastContext.objectCount);
        boolean[] inspected = new boolean[objectCount + 1];
        boolean[] manipulated = new boolean[objectCount + 1];

        for (ActionEvent e : trace.actions) {
            if (e.objectIndex < 1 || e.objectIndex > objectCount) {
                continue;
            }

            if (e.phase == Phase.EXPLORATION) {
                if (e.functionalType == FunctionalType.LOOK) {
                    inspected[e.objectIndex] = true;
                }

                if (e.functionalType == FunctionalType.INTERACT) {
                    manipulated[e.objectIndex] = true;
                }
            }
        }

        r.inspectionCoverage = ((double) countTrue(inspected)) / (double) objectCount;
        r.manipulationCoverage = ((double) countTrue(manipulated)) / (double) objectCount;

        ActionEvent firstProbeInteraction = firstInteractionInPhase(trace, Phase.PROBE);

        if (firstProbeInteraction != null
                && firstProbeInteraction.objectIndex == trace.lastContext.goalObject) {
            r.firstAttemptAccuracy = 1;
        } else {
            r.firstAttemptAccuracy = 0;
        }

        if (firstProbeInteraction != null
                && firstProbeInteraction.objectIndex == trace.lastContext.goalObject) {
            int actionsBeforeGoal = countEffectiveActionsUntilObjectInPhase(
                    trace,
                    trace.lastContext.goalObject,
                    Phase.PROBE
            );

            r.firstInteractionEfficiency = 1.0 / Math.max(1, actionsBeforeGoal);
        } else {
            r.firstInteractionEfficiency = 0.0;
        }

        ActionEvent firstGoalLook = firstLookAtObjectInPhase(
                trace,
                trace.lastContext.goalObject,
                Phase.PROBE
        );

        if (firstGoalLook != null) {
            r.firstGoalFixLatencyCycles =
                    firstGoalLook.cycle - safePhaseStart(firstGoalLook);
        }

        if (firstProbeInteraction != null
                && firstProbeInteraction.objectIndex == trace.lastContext.goalObject) {
            r.firstGoalInteractionLatencyCycles =
                    firstProbeInteraction.cycle - safePhaseStart(firstProbeInteraction);
        }

        return r;
    }

    private MotivationEvaluationReport.TrialResult evaluateOutcomeDevaluation(MotivationData.TrialTrace trace) {
        MotivationEvaluationReport.TrialResult r = buildBaseResult(trace);

        ActionEvent firstExtinctionInteraction = firstInteractionInPhase(trace, Phase.EXTINCTION);

        if (firstExtinctionInteraction == null) {
            r.devaluationSensitivity = 0.5;
            r.responseSuppression = 1.0;
            return r;
        }

        if (firstExtinctionInteraction.objectIndex == trace.lastContext.devaluedObject) {
            r.devaluationSensitivity = 0.0;
            r.responseSuppression = 0.0;
        } else if (firstExtinctionInteraction.objectIndex == trace.lastContext.goalObject
                || firstExtinctionInteraction.objectIndex == trace.lastContext.alternativeObject) {
            r.devaluationSensitivity = 1.0;
            r.responseSuppression = 1.0;
        } else {
            r.devaluationSensitivity = 0.5;
            r.responseSuppression = 0.5;
        }

        return r;
    }

    private MotivationEvaluationReport.TrialResult buildBaseResult(MotivationData.TrialTrace trace) {
        MotivationData.TrialContext c = trace.lastContext;
        MotivationEvaluationReport.TrialResult r = new MotivationEvaluationReport.TrialResult();

        r.motivationExperimentId = motivationExperimentId;
        r.experimentId = experimentName(motivationExperimentId);
        r.episode = c.episode;
        r.trialId = c.trialId;
        r.condition = c.condition == null ? "" : c.condition;

        r.targetObject = c.targetObject;
        r.targetObjectLabel = c.targetLabel;
        r.targetRole = c.targetRole;

        r.alternativeObject = c.alternativeObject;
        r.alternativeObjectLabel = c.alternativeLabel;

        r.controlObject = c.controlObject;
        r.controlObjectLabel = c.controlLabel;

        r.goalObject = c.goalObject;
        r.goalObjectLabel = c.goalLabel;

        r.devaluedObject = c.devaluedObject;
        r.devaluedObjectLabel = c.devaluedLabel;

        ActionEvent firstAction = trace.firstAction();
        ActionEvent firstLook = trace.firstLook();
        ActionEvent firstInteraction = trace.firstInteraction();

        if (firstAction != null) {
            r.firstRawAction = firstAction.actionId == null ? "" : firstAction.actionId.id;
            r.firstActionCategory = firstAction.category == null ? "" : firstAction.category.name();
            r.firstFunctionalAction = firstAction.functionalType == null ? "" : firstAction.functionalType.name();
            r.firstResponseObject = firstAction.objectIndex;
            r.firstResponseObjectLabel = firstAction.objectLabel;
        }

        if (firstLook != null) {
            r.firstLookObject = firstLook.objectIndex;
            r.firstLookObjectLabel = firstLook.objectLabel;
            r.firstLookLatencyCycles = firstLook.cycle - safePhaseStart(firstLook);
        }

        if (firstInteraction != null) {
            r.firstInteractionObject = firstInteraction.objectIndex;
            r.firstInteractionObjectLabel = firstInteraction.objectLabel;
            r.firstInteractionRole = firstInteraction.objectRole;
            r.firstInteractionLatencyCycles = firstInteraction.cycle - safePhaseStart(firstInteraction);
        }

        r.rawActionCount = trace.actions.size();
        r.motorActionCount = trace.countByCategory(Category.MOTOR);
        r.virtualActionCount = trace.countByCategory(Category.VIRTUAL);
        r.attentionalActionCount = trace.countByCategory(Category.ATTENTIONAL);
        r.lookCount = trace.countLooks();
        r.interactionCount = trace.countInteractions();
        r.omission = firstAction == null;

        return r;
    }

    private long safePhaseStart(ActionEvent event) {
        if (event == null || event.phaseStartCycle < 0L) {
            return 0L;
        }

        return event.phaseStartCycle;
    }

    private ActionEvent firstInteractionInPhase(MotivationData.TrialTrace trace, Phase phase) {
        for (ActionEvent e : trace.actions) {
            if (e.phase == phase && e.functionalType == FunctionalType.INTERACT) {
                return e;
            }
        }

        return null;
    }

    private ActionEvent firstLookAtObjectInPhase(
            MotivationData.TrialTrace trace,
            int objectIndex,
            Phase phase
    ) {
        for (ActionEvent e : trace.actions) {
            if (e.phase == phase
                    && e.objectIndex == objectIndex
                    && e.functionalType == FunctionalType.LOOK) {
                return e;
            }
        }

        return null;
    }

    private int countEffectiveActionsUntilObjectInPhase(
            MotivationData.TrialTrace trace,
            int objectIndex,
            Phase phase
    ) {
        int n = 0;

        for (ActionEvent e : trace.actions) {
            if (e.phase != phase) {
                continue;
            }

            if (e.functionalType == FunctionalType.LOOK
                    || e.functionalType == FunctionalType.INTERACT) {
                n++;
            }

            if (e.objectIndex == objectIndex
                    && e.functionalType == FunctionalType.INTERACT) {
                return n;
            }
        }

        return n;
    }

    private int countTrue(boolean[] values) {
        int n = 0;

        if (values == null) {
            return 0;
        }

        for (boolean v : values) {
            if (v) {
                n++;
            }
        }

        return n;
    }

    public static String experimentName(int id) {
        switch (id) {
            case EXP1_PERSISTENCE:
                return "exp1_persistence_without_stimulus";
            case EXP2_DEPRIVATION_SATIATION:
                return "exp2_deprivation_satiation_modulation";
            case EXP3_GOAL_SUBSTITUTION:
                return "exp3_goal_substitution_detour";
            case EXP4_LATENT_LEARNING:
                return "exp4_tabletop_latent_learning";
            case EXP5_OUTCOME_DEVALUATION:
                return "exp5_outcome_devaluation";
            default:
                return "motivation_experiment";
        }
    }

    private void writePerTrialCsv(MotivationEvaluationReport.Summary summary) throws IOException {
        File file = new File(
                config.outDir,
                safeName(config.filePrefix)
                        + "_exp"
                        + summary.motivationExperimentId
                        + "_"
                        + safeName(summary.experimentId)
                        + "_per_trial_episode_"
                        + summary.episode
                        + "_"
                        + safeName(summary.architectureName)
                        + ".csv"
        );

        PrintWriter pw = new PrintWriter(new FileWriter(file, false));

        try {
            pw.println(
                    "motivation_experiment_id,experiment_id,architecture,episode,trial_id,condition,"
                            + "target_object,target_label,target_role,alternative_object,alternative_label,"
                            + "control_object,control_label,goal_object,goal_label,devalued_object,devalued_label,"
                            + "first_raw_action,first_action_category,first_functional_action,"
                            + "first_response_object,first_response_label,first_look_object,first_look_label,"
                            + "first_interaction_object,first_interaction_label,first_interaction_role,"
                            + "first_look_latency_cycles,first_interaction_latency_cycles,"
                            + "first_goal_fix_latency_cycles,first_goal_interaction_latency_cycles,"
                            + "raw_action_count,motor_action_count,virtual_action_count,attentional_action_count,"
                            + "look_count,interaction_count,persistence_duration_cycles,persistence_selectivity,"
                            + "resource_choice,novelty_choice,control_choice,substitution_success,perseveration,"
                            + "detour_efficiency,inspection_coverage,manipulation_coverage,first_attempt_accuracy,"
                            + "first_interaction_efficiency,devaluation_sensitivity,response_suppression,omission"
            );

            for (MotivationEvaluationReport.TrialResult r : summary.trials) {
                pw.printf(
                        Locale.US,
                        "%d,%s,%s,%d,%s,%s,%d,%s,%s,%d,%s,%d,%s,%d,%s,%d,%s,%s,%s,%s,%d,%s,%d,%s,%d,%s,%s,%s,%s,%s,%s,%d,%d,%d,%d,%d,%d,%s,%s,%d,%d,%d,%d,%s,%s,%s,%s,%d,%s,%s,%s,%s%n",
                        r.motivationExperimentId,
                        csv(r.experimentId),
                        csv(r.architectureName),
                        r.episode,
                        csv(r.trialId),
                        csv(r.condition),
                        r.targetObject,
                        csv(r.targetObjectLabel),
                        csv(r.targetRole),
                        r.alternativeObject,
                        csv(r.alternativeObjectLabel),
                        r.controlObject,
                        csv(r.controlObjectLabel),
                        r.goalObject,
                        csv(r.goalObjectLabel),
                        r.devaluedObject,
                        csv(r.devaluedObjectLabel),
                        csv(r.firstRawAction),
                        csv(r.firstActionCategory),
                        csv(r.firstFunctionalAction),
                        r.firstResponseObject,
                        csv(r.firstResponseObjectLabel),
                        r.firstLookObject,
                        csv(r.firstLookObjectLabel),
                        r.firstInteractionObject,
                        csv(r.firstInteractionObjectLabel),
                        csv(r.firstInteractionRole),
                        nullableLong(r.firstLookLatencyCycles),
                        nullableLong(r.firstInteractionLatencyCycles),
                        nullableLong(r.firstGoalFixLatencyCycles),
                        nullableLong(r.firstGoalInteractionLatencyCycles),
                        r.rawActionCount,
                        r.motorActionCount,
                        r.virtualActionCount,
                        r.attentionalActionCount,
                        r.lookCount,
                        r.interactionCount,
                        nullableDoubleValue(r.persistenceDurationCycles),
                        nullableDoubleValue(r.persistenceSelectivity),
                        r.resourceChoice,
                        r.noveltyChoice,
                        r.controlChoice,
                        r.substitutionSuccess,
                        nullableDoubleValue(r.perseveration),
                        nullableDoubleValue(r.detourEfficiency),
                        nullableDoubleValue(r.inspectionCoverage),
                        nullableDoubleValue(r.manipulationCoverage),
                        r.firstAttemptAccuracy,
                        nullableDoubleValue(r.firstInteractionEfficiency),
                        nullableDoubleValue(r.devaluationSensitivity),
                        nullableDoubleValue(r.responseSuppression),
                        Boolean.toString(r.omission)
                );
            }
        } finally {
            pw.flush();
            pw.close();
        }

        printSavedFile(file);
    }

    private void writeSummaryCsv(MotivationEvaluationReport.Summary summary) throws IOException {
        File file = new File(
                config.outDir,
                safeName(config.filePrefix)
                        + "_exp"
                        + summary.motivationExperimentId
                        + "_"
                        + safeName(summary.experimentId)
                        + "_summary_episode_"
                        + summary.episode
                        + "_"
                        + safeName(summary.architectureName)
                        + ".csv"
        );

        PrintWriter pw = new PrintWriter(new FileWriter(file, false));

        try {
            pw.println(
                    "motivation_experiment_id,experiment_id,architecture,episode,aborted,total_trials,"
                            + "mean_persistence_duration_cycles,mean_persistence_selectivity,"
                            + "resource_choice_probability,novelty_choice_probability,control_choice_probability,"
                            + "resource_modulation_index,novelty_modulation_index,"
                            + "substitution_success_rate,mean_perseveration,mean_detour_efficiency,"
                            + "mean_inspection_coverage,mean_manipulation_coverage,first_attempt_accuracy_rate,"
                            + "mean_first_interaction_efficiency,latent_learning_gain_efficiency,"
                            + "latent_learning_gain_latency,mean_devaluation_sensitivity,mean_response_suppression,"
                            + "mean_motor_action_count,mean_virtual_action_count,mean_attentional_action_count,"
                            + "omission_rate,behavioral_motivation_score"
            );

            pw.printf(
                    Locale.US,
                    "%d,%s,%s,%d,%s,%d,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s%n",
                    summary.motivationExperimentId,
                    csv(summary.experimentId),
                    csv(summary.architectureName),
                    summary.episode,
                    Boolean.toString(summary.aborted),
                    summary.totalTrials,
                    nullableDoubleValue(summary.meanPersistenceDurationCycles),
                    nullableDoubleValue(summary.meanPersistenceSelectivity),
                    nullableDoubleValue(summary.resourceChoiceProbability),
                    nullableDoubleValue(summary.noveltyChoiceProbability),
                    nullableDoubleValue(summary.controlChoiceProbability),
                    nullableDoubleValue(summary.resourceModulationIndex),
                    nullableDoubleValue(summary.noveltyModulationIndex),
                    nullableDoubleValue(summary.substitutionSuccessRate),
                    nullableDoubleValue(summary.meanPerseveration),
                    nullableDoubleValue(summary.meanDetourEfficiency),
                    nullableDoubleValue(summary.meanInspectionCoverage),
                    nullableDoubleValue(summary.meanManipulationCoverage),
                    nullableDoubleValue(summary.firstAttemptAccuracyRate),
                    nullableDoubleValue(summary.meanFirstInteractionEfficiency),
                    nullableDoubleValue(summary.latentLearningGainEfficiency),
                    nullableDoubleValue(summary.latentLearningGainLatency),
                    nullableDoubleValue(summary.meanDevaluationSensitivity),
                    nullableDoubleValue(summary.meanResponseSuppression),
                    nullableDoubleValue(summary.meanMotorActionCount),
                    nullableDoubleValue(summary.meanVirtualActionCount),
                    nullableDoubleValue(summary.meanAttentionalActionCount),
                    nullableDoubleValue(summary.omissionRate),
                    nullableDoubleValue(summary.behavioralMotivationScore)
            );
        } finally {
            pw.flush();
            pw.close();
        }

        printSavedFile(file);
    }

    private double computeBehavioralMotivationScore(MotivationEvaluationReport.Summary s) {
        List<Double> values = new ArrayList<Double>();

        addIfFinite(values, s.meanPersistenceSelectivity);
        addIfFinite(values, positiveClamp(s.resourceModulationIndex));
        addIfFinite(values, positiveClamp(s.noveltyModulationIndex));
        addIfFinite(values, s.substitutionSuccessRate);
        addIfFinite(values, positiveClamp(s.latentLearningGainEfficiency));
        addIfFinite(values, s.meanDevaluationSensitivity);

        return mean(values);
    }

    private double choiceProbabilityByConditionAndRole(
            List<MotivationEvaluationReport.TrialResult> trials,
            String condition,
            String role
    ) {
        int n = 0;
        int yes = 0;

        for (MotivationEvaluationReport.TrialResult r : trials) {
            if (r.condition == null || !r.condition.equals(condition)) {
                continue;
            }

            n++;

            if (r.firstInteractionRole != null
                    && r.firstInteractionRole.equalsIgnoreCase(role)) {
                yes++;
            }
        }

        if (n == 0) {
            return Double.NaN;
        }

        return ((double) yes) / (double) n;
    }

    private double meanEfficiencyByCondition(
            List<MotivationEvaluationReport.TrialResult> trials,
            String condition
    ) {
        List<Double> values = new ArrayList<Double>();

        for (MotivationEvaluationReport.TrialResult r : trials) {
            if (r.condition != null
                    && r.condition.equals(condition)
                    && isFinite(r.firstInteractionEfficiency)) {
                values.add(Double.valueOf(r.firstInteractionEfficiency));
            }
        }

        return mean(values);
    }

    private double meanGoalInteractionLatencyByCondition(
            List<MotivationEvaluationReport.TrialResult> trials,
            String condition
    ) {
        List<Double> values = new ArrayList<Double>();

        for (MotivationEvaluationReport.TrialResult r : trials) {
            if (r.condition == null || !r.condition.equals(condition)) {
                continue;
            }

            if (r.firstGoalInteractionLatencyCycles != null) {
                values.add(Double.valueOf(r.firstGoalInteractionLatencyCycles.doubleValue()));
            }
        }

        return mean(values);
    }

    private double meanBooleanOmission(List<MotivationEvaluationReport.TrialResult> trials) {
        if (trials == null || trials.isEmpty()) {
            return Double.NaN;
        }

        int n = 0;
        int omissions = 0;

        for (MotivationEvaluationReport.TrialResult r : trials) {
            n++;
            if (r.omission) {
                omissions++;
            }
        }

        return ((double) omissions) / (double) n;
    }

    private double meanField(
            List<MotivationEvaluationReport.TrialResult> trials,
            String fieldName
    ) {
        List<Double> values = new ArrayList<Double>();

        for (MotivationEvaluationReport.TrialResult r : trials) {
            try {
                Field f = MotivationEvaluationReport.TrialResult.class.getField(fieldName);
                Object raw = f.get(r);

                if (raw instanceof Number) {
                    double v = ((Number) raw).doubleValue();

                    if (isFinite(v)) {
                        values.add(Double.valueOf(v));
                    }
                }
            } catch (Exception ignored) {
            }
        }

        return mean(values);
    }

    private double meanIntField(
            List<MotivationEvaluationReport.TrialResult> trials,
            String fieldName
    ) {
        List<Double> values = new ArrayList<Double>();

        for (MotivationEvaluationReport.TrialResult r : trials) {
            try {
                Field f = MotivationEvaluationReport.TrialResult.class.getField(fieldName);
                Object raw = f.get(r);

                if (raw instanceof Number) {
                    values.add(Double.valueOf(((Number) raw).doubleValue()));
                }
            } catch (Exception ignored) {
            }
        }

        return mean(values);
    }

    private double mean(List<Double> values) {
        if (values == null || values.isEmpty()) {
            return Double.NaN;
        }

        double sum = 0.0;
        int n = 0;

        for (Double v : values) {
            if (v != null && isFinite(v.doubleValue())) {
                sum += v.doubleValue();
                n++;
            }
        }

        if (n == 0) {
            return Double.NaN;
        }

        return sum / (double) n;
    }

    private void addIfFinite(List<Double> values, double v) {
        if (isFinite(v)) {
            values.add(Double.valueOf(v));
        }
    }

    private double positiveClamp(double v) {
        if (!isFinite(v)) {
            return Double.NaN;
        }

        if (v < 0.0) {
            return 0.0;
        }

        if (v > 1.0) {
            return 1.0;
        }

        return v;
    }

    private void validateExperimentId(int id) {
        if (id < EXP1_PERSISTENCE || id > EXP5_OUTCOME_DEVALUATION) {
            throw new IllegalArgumentException(
                    "Motivation experiment id must be between 1 and 5. Received: " + id
            );
        }
    }

    private boolean isFinite(double v) {
        return !Double.isNaN(v) && !Double.isInfinite(v);
    }

    private String lower(String s) {
        return s == null ? "" : s.trim().toLowerCase();
    }

    private String blankToDefault(String s, String fallback) {
        if (s == null || s.trim().isEmpty()) {
            return fallback;
        }

        return s;
    }

    private String safeName(String s) {
        if (s == null || s.trim().isEmpty()) {
            return "unknown";
        }

        return s.replaceAll("[^a-zA-Z0-9_\\-\\.]", "_");
    }

    private String csv(String s) {
        if (s == null) {
            return "";
        }

        return s.replace(",", "_").replace("\n", " ").replace("\r", " ");
    }

    private String nullableLong(Long v) {
        return v == null ? "" : Long.toString(v.longValue());
    }

    private String nullableDoubleValue(double v) {
        if (!isFinite(v)) {
            return "";
        }

        return String.format(Locale.US, "%.10f", v);
    }

    private void printSavedFile(File file) {
        if (file == null) {
            return;
        }

        String path;

        try {
            path = file.getCanonicalPath();
        } catch (IOException e) {
            path = file.getAbsolutePath();
        }

        System.out.println("[MotivationTestRunner] saved: " + path);
    }
}
