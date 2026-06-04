package org.cst.cogscore.modules.attention;

import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.io.PrintWriter;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TreeMap;

public class PosnerAttentionTestRunner {

    public static final int EXP1_CENTRAL_CUE = 1;
    public static final int EXP2_SOA_SWEEP = 2;
    public static final int EXP3_PERIPHERAL_CAPTURE = 3;
    public static final int EXP4_VISUAL_SEARCH = 4;
    public static final int EXP5_CROWDING = 5;

    public static final class Config {
        public double matchToleranceNormalized = 0.15;
        public double attentionBiasThreshold = 0.05;
        public Double detectionThreshold = null;
        public boolean useDetectionFrameAsReference = true;
        public File outDir = new File("attention_posner_out");
        public String filePrefix = "attention_posner";

        /*
         * A high-entropy, almost-uniform attention map should not be interpreted
         * as a spatially focused detection or orienting event.
         */
        public double neutralEntropyMin = 0.98;

        /*
         * Alternative neutral-map test. If variance is extremely small, the map is
         * treated as neutral/uniform.
         */
        public double neutralVarianceThreshold = 1e-6;

        public Config setMatchToleranceNormalized(double v) {
            this.matchToleranceNormalized = v;
            return this;
        }

        public Config setAttentionBiasThreshold(double v) {
            this.attentionBiasThreshold = v;
            return this;
        }

        public Config setDetectionThreshold(Double v) {
            this.detectionThreshold = v;
            return this;
        }

        public Config setUseDetectionFrameAsReference(boolean v) {
            this.useDetectionFrameAsReference = v;
            return this;
        }

        public Config setOutDir(File outDir) {
            this.outDir = outDir;
            return this;
        }

        public Config setFilePrefix(String filePrefix) {
            this.filePrefix = filePrefix;
            return this;
        }

        public Config setNeutralEntropyMin(double v) {
            this.neutralEntropyMin = v;
            return this;
        }

        public Config setNeutralVarianceThreshold(double v) {
            this.neutralVarianceThreshold = v;
            return this;
        }
    }

    private final int posnerExperimentId;
    private final Config config;

    public PosnerAttentionTestRunner(int posnerExperimentId, Config config) {
        validateExperimentId(posnerExperimentId);
        this.posnerExperimentId = posnerExperimentId;
        this.config = config == null ? new Config() : config;
        if (this.config.outDir != null && !this.config.outDir.exists()) {
            this.config.outDir.mkdirs();
        }
    }

    public AttentionEvaluationReport.TrialResult evaluate(AttentionData.TrialInput input) {
        validateInput(input);

        switch (posnerExperimentId) {
            case EXP1_CENTRAL_CUE:
                return evaluateStandardTrial(input);
            case EXP2_SOA_SWEEP:
                return evaluateStandardTrial(input);
            case EXP3_PERIPHERAL_CAPTURE:
                return evaluatePeripheralCaptureTrial(input);
            case EXP4_VISUAL_SEARCH:
                return evaluateVisualSearchTrial(input);
            case EXP5_CROWDING:
                return evaluateCrowdingTrial(input);
            default:
                throw new IllegalStateException("Unsupported Posner experiment id: " + posnerExperimentId);
        }
    }

    public AttentionEvaluationReport.Summary evaluateAll(
            String architectureName,
            int episode,
            boolean aborted,
            List<AttentionData.TrialInput> inputs
    ) throws IOException {
        List<AttentionEvaluationReport.TrialResult> results = new ArrayList<AttentionEvaluationReport.TrialResult>();
        if (inputs != null) {
            for (AttentionData.TrialInput input : inputs) {
                results.add(evaluate(input));
            }
        }
        AttentionEvaluationReport.Summary summary = summarize(architectureName, episode, aborted, results);
        writeEpisodeFiles(summary);
        return summary;
    }

    public AttentionEvaluationReport.Summary summarize(
            String architectureName,
            int episode,
            boolean aborted,
            List<AttentionEvaluationReport.TrialResult> results
    ) {
        AttentionEvaluationReport.Summary summary = new AttentionEvaluationReport.Summary();
        summary.posnerExperimentId = posnerExperimentId;
        summary.experimentId = experimentName(posnerExperimentId);
        summary.architectureName = blankToDefault(architectureName, "unknown");
        summary.episode = episode;
        summary.aborted = aborted;

        if (results != null) {
            summary.trials.addAll(results);
        }

        summary.totalTrials = summary.trials.size();

        summary.meanRtValid = meanReactionTime(summary.trials, AttentionData.TrialType.VALID);
        summary.meanRtInvalid = meanReactionTime(summary.trials, AttentionData.TrialType.INVALID);
        summary.meanRtNeutral = meanReactionTime(summary.trials, AttentionData.TrialType.NEUTRAL);

        if (isFinite(summary.meanRtNeutral) && isFinite(summary.meanRtValid)) {
            summary.benefit = summary.meanRtNeutral - summary.meanRtValid;
        }
        if (isFinite(summary.meanRtInvalid) && isFinite(summary.meanRtNeutral)) {
            summary.cost = summary.meanRtInvalid - summary.meanRtNeutral;
        }
        if (isFinite(summary.meanRtInvalid) && isFinite(summary.meanRtValid)) {
            summary.validityEffect = summary.meanRtInvalid - summary.meanRtValid;
        }

        summary.meanInitialFidelityOverall = meanInitialFidelity(summary.trials, null);
        summary.meanFinalFidelityOverall = meanFinalFidelity(summary.trials, null);
        summary.meanFinalFidelityValid = meanFinalFidelity(summary.trials, AttentionData.TrialType.VALID);
        summary.meanFinalFidelityInvalid = meanFinalFidelity(summary.trials, AttentionData.TrialType.INVALID);
        summary.meanFinalFidelityNeutral = meanFinalFidelity(summary.trials, AttentionData.TrialType.NEUTRAL);

        if (posnerExperimentId == EXP2_SOA_SWEEP) {
            fillSoaMetrics(summary);
        }
        if (posnerExperimentId == EXP3_PERIPHERAL_CAPTURE) {
            fillPeripheralMetrics(summary);
        }
        if (posnerExperimentId == EXP4_VISUAL_SEARCH) {
            fillVisualSearchMetrics(summary);
        }
        if (posnerExperimentId == EXP5_CROWDING) {
            fillCrowdingMetrics(summary);
        }

        return summary;
    }

    private void printSavedFile(File file) {
        if (file == null) return;

        String path;
        try {
            path = file.getCanonicalPath();
        } catch (IOException e) {
            path = file.getAbsolutePath();
        }

        System.out.println("[PosnerAttentionTestRunner] saved: " + path);
    }
    
    public void writeEpisodeFiles(AttentionEvaluationReport.Summary summary) throws IOException {
        if (summary == null) return;

        if (config.outDir == null) {
            config.outDir = new File("attention_posner_out");
        }

        if (!config.outDir.exists() && !config.outDir.mkdirs()) {
            throw new IOException("Could not create output directory: "
                    + config.outDir.getAbsolutePath());
        }

        writePerTrialCsv(summary);
        writeSummaryCsv(summary);
        writeSoaCsv(summary);
        writeCrowdingCsv(summary);
    }

    private AttentionEvaluationReport.TrialResult evaluateStandardTrial(AttentionData.TrialInput input) {
        List<AttentionData.Frame> frames = sortedFrames(input);
        Long detectionCycle = resolveDetectionCycle(input, frames);
        AttentionData.Frame initialFrame = chooseInitialFrame(input, frames);
        AttentionData.Frame referenceFrame = chooseReferenceFrame(frames, detectionCycle);
        AttentionData.Frame focusFrame = referenceFrame == null ? initialFrame : referenceFrame;

        return buildBaseResult(input, frames, initialFrame, focusFrame, detectionCycle);
    }

    private AttentionEvaluationReport.TrialResult evaluatePeripheralCaptureTrial(AttentionData.TrialInput input) {
        AttentionEvaluationReport.TrialResult result = evaluateStandardTrial(input);
        List<AttentionData.Frame> frames = sortedFrames(input);

        AttentionData.Point cuePoint = input.cueNormalized == null ? input.targetNormalized : input.cueNormalized;
        Long orientingCycle = firstBiasCycle(frames, cuePoint, input.fixationNormalized, input.cueOnsetCycle);

        if (orientingCycle != null && input.cueOnsetCycle != null) {
            result.bottomUpLatencyCycles = (double) (orientingCycle.longValue() - input.cueOnsetCycle.longValue());
            result.attentionLatencyCycles = result.bottomUpLatencyCycles;
        }

        if (input.overtMovementCycle != null && input.cueOnsetCycle != null
                && input.overtMovementCycle.longValue() >= input.cueOnsetCycle.longValue()) {
            result.eyeMovementLatencyCycles =
                    (double) (input.overtMovementCycle.longValue() - input.cueOnsetCycle.longValue());
        }

        return result;
    }

    private AttentionEvaluationReport.TrialResult evaluateVisualSearchTrial(AttentionData.TrialInput input) {
        if (input.searchType == AttentionData.SearchType.NONE) {
            throw new IllegalArgumentException("Experiment 4 requires input.searchType FEATURE or CONJUNCTION");
        }
        if (input.distractorCount == null) {
            throw new IllegalArgumentException("Experiment 4 requires input.distractorCount");
        }
        return evaluateStandardTrial(input);
    }

    private AttentionEvaluationReport.TrialResult evaluateCrowdingTrial(AttentionData.TrialInput input) {
        if (input.flanked == null) {
            throw new IllegalArgumentException("Experiment 5 requires input.flanked");
        }
        if (Boolean.TRUE.equals(input.flanked) && input.flankerDistance == null) {
            throw new IllegalArgumentException("Experiment 5 requires input.flankerDistance for flanked trials");
        }
        return evaluateStandardTrial(input);
    }

    private AttentionEvaluationReport.TrialResult buildBaseResult(
            AttentionData.TrialInput input,
            List<AttentionData.Frame> frames,
            AttentionData.Frame initialFrame,
            AttentionData.Frame focusFrame,
            Long detectionCycle
    ) {
        AttentionData.Point focus = focusFrame.getPeakNormalized();
        Long orientingCycle = firstBiasCycle(frames, input.targetNormalized, input.fixationNormalized, input.cueOnsetCycle);

        AttentionEvaluationReport.TrialResult result = new AttentionEvaluationReport.TrialResult();

        result.posnerExperimentId = posnerExperimentId;
        result.episode = input.episode;
        result.trialId = safeTrialId(input.trialId, input, frames);
        result.modality = blankToDefault(input.modality, "attention");
        result.cueType = input.cueType;
        result.trialType = input.trialType;
        result.searchType = input.searchType;

        result.width = initialFrame.getWidth();
        result.height = initialFrame.getHeight();
        result.frameCount = frames.size();

        result.cueOnsetCycle = input.cueOnsetCycle;
        result.targetOnsetCycle = input.targetOnsetCycle;
        result.detectionCycle = detectionCycle;
        result.overtMovementCycle = input.overtMovementCycle;
        result.reactionTimeCycles = computeReactionTime(input, detectionCycle);
        result.soaMs = input.soaMs;

        if (orientingCycle != null && input.cueOnsetCycle != null
                && orientingCycle.longValue() >= input.cueOnsetCycle.longValue()) {
            result.attentionLatencyCycles =
                    (double) (orientingCycle.longValue() - input.cueOnsetCycle.longValue());
        }

        result.distractorCount = input.distractorCount;
        result.flanked = input.flanked;
        result.flankerDistance = input.flankerDistance;

        result.targetX = input.targetNormalized.getX();
        result.targetY = input.targetNormalized.getY();

        if (input.cueNormalized != null) {
            result.cueX = input.cueNormalized.getX();
            result.cueY = input.cueNormalized.getY();
        }

        if (input.fixationNormalized != null) {
            result.fixationX = input.fixationNormalized.getX();
            result.fixationY = input.fixationNormalized.getY();
        }

        result.focusX = focus.getX();
        result.focusY = focus.getY();

        result.peakValue = focusFrame.getPeakValue();
        result.mapVariance = focusFrame.variance();
        result.normalizedEntropy = focusFrame.normalizedEntropy();

        result.initialFidelity = fidelity(initialFrame, input.targetNormalized);
        result.finalFidelity = fidelity(focusFrame, input.targetNormalized);

        return result;
    }

    private void fillSoaMetrics(AttentionEvaluationReport.Summary summary) {
        TreeMap<Double, List<AttentionEvaluationReport.TrialResult>> bySoa =
                new TreeMap<Double, List<AttentionEvaluationReport.TrialResult>>();

        for (AttentionEvaluationReport.TrialResult r : summary.trials) {
            if (r.soaMs == null || !isFinite(r.soaMs.doubleValue())) continue;

            List<AttentionEvaluationReport.TrialResult> list = bySoa.get(r.soaMs);
            if (list == null) {
                list = new ArrayList<AttentionEvaluationReport.TrialResult>();
                bySoa.put(r.soaMs, list);
            }
            list.add(r);
        }

        for (Map.Entry<Double, List<AttentionEvaluationReport.TrialResult>> entry : bySoa.entrySet()) {
            double valid = meanReactionTime(entry.getValue(), AttentionData.TrialType.VALID);
            double neutral = meanReactionTime(entry.getValue(), AttentionData.TrialType.NEUTRAL);
            double invalid = meanReactionTime(entry.getValue(), AttentionData.TrialType.INVALID);

            double benefit = Double.NaN;
            double cost = Double.NaN;

            if (isFinite(neutral) && isFinite(valid)) {
                benefit = neutral - valid;
            }
            if (isFinite(invalid) && isFinite(neutral)) {
                cost = invalid - neutral;
            }

            summary.soaValues.add(entry.getKey());
            summary.benefitBySoa.add(benefit);
            summary.costBySoa.add(cost);

            if (summary.topDownOrientingLatency == null
                    && isFinite(valid)
                    && isFinite(neutral)
                    && valid < neutral) {
                summary.topDownOrientingLatency = entry.getKey();
            }
        }
    }

    private void fillPeripheralMetrics(AttentionEvaluationReport.Summary summary) {
        List<Double> bu = new ArrayList<Double>();
        List<Double> eye = new ArrayList<Double>();
        List<Double> cuedRt = new ArrayList<Double>();
        List<Double> uncuedRt = new ArrayList<Double>();

        for (AttentionEvaluationReport.TrialResult r : summary.trials) {
            if (r.bottomUpLatencyCycles != null && isFinite(r.bottomUpLatencyCycles.doubleValue())) {
                bu.add(r.bottomUpLatencyCycles);
            }
            if (r.eyeMovementLatencyCycles != null && isFinite(r.eyeMovementLatencyCycles.doubleValue())) {
                eye.add(r.eyeMovementLatencyCycles);
            }
            if (r.reactionTimeCycles != null && isFinite(r.reactionTimeCycles.doubleValue())) {
                if (r.trialType == AttentionData.TrialType.VALID) {
                    cuedRt.add(r.reactionTimeCycles);
                } else if (r.trialType == AttentionData.TrialType.INVALID) {
                    uncuedRt.add(r.reactionTimeCycles);
                }
            }
        }

        summary.meanBottomUpLatency = nullableMean(bu);
        summary.meanEyeMovementLatency = nullableMean(eye);
        summary.meanRtCued = nullableMean(cuedRt);
        summary.meanRtUncued = nullableMean(uncuedRt);
    }

    private void fillVisualSearchMetrics(AttentionEvaluationReport.Summary summary) {
        summary.featureSearchSlope = slopeForSearchType(summary.trials, AttentionData.SearchType.FEATURE);
        summary.conjunctionSearchSlope = slopeForSearchType(summary.trials, AttentionData.SearchType.CONJUNCTION);
    }

    private void fillCrowdingMetrics(AttentionEvaluationReport.Summary summary) {
        double unflankedOverall = meanRtFlanked(summary.trials, Boolean.FALSE, null, null);

        TreeMap<Double, List<AttentionEvaluationReport.TrialResult>> byDistance =
                new TreeMap<Double, List<AttentionEvaluationReport.TrialResult>>();

        for (AttentionEvaluationReport.TrialResult r : summary.trials) {
            if (!Boolean.TRUE.equals(r.flanked)) continue;
            if (r.flankerDistance == null || !isFinite(r.flankerDistance.doubleValue())) continue;

            List<AttentionEvaluationReport.TrialResult> list = byDistance.get(r.flankerDistance);
            if (list == null) {
                list = new ArrayList<AttentionEvaluationReport.TrialResult>();
                byDistance.put(r.flankerDistance, list);
            }
            list.add(r);
        }

        for (Map.Entry<Double, List<AttentionEvaluationReport.TrialResult>> entry : byDistance.entrySet()) {
            double flankedOverall = meanRt(entry.getValue());
            double crowdingCost = Double.NaN;

            if (isFinite(flankedOverall) && isFinite(unflankedOverall)) {
                crowdingCost = flankedOverall - unflankedOverall;
            }

            double neutralFlanked = meanReactionTime(entry.getValue(), AttentionData.TrialType.NEUTRAL);
            double validFlanked = meanReactionTime(entry.getValue(), AttentionData.TrialType.VALID);
            double neutralUnflanked = meanRtFlanked(summary.trials, Boolean.FALSE, AttentionData.TrialType.NEUTRAL, null);
            double validUnflanked = meanRtFlanked(summary.trials, Boolean.FALSE, AttentionData.TrialType.VALID, null);

            double ccNeutral = Double.NaN;
            double ccValid = Double.NaN;
            double arc = Double.NaN;

            if (isFinite(neutralFlanked) && isFinite(neutralUnflanked)) {
                ccNeutral = neutralFlanked - neutralUnflanked;
            }
            if (isFinite(validFlanked) && isFinite(validUnflanked)) {
                ccValid = validFlanked - validUnflanked;
            }
            if (isFinite(ccNeutral) && isFinite(ccValid)) {
                arc = ccNeutral - ccValid;
            }

            summary.flankerDistances.add(entry.getKey());
            summary.crowdingCostByDistance.add(crowdingCost);
            summary.attentionalReductionByDistance.add(arc);
        }
    }

    private List<AttentionData.Frame> sortedFrames(AttentionData.TrialInput input) {
        List<AttentionData.Frame> frames = new ArrayList<AttentionData.Frame>(input.frames);
        Collections.sort(frames, new Comparator<AttentionData.Frame>() {
            @Override
            public int compare(AttentionData.Frame a, AttentionData.Frame b) {
                return Long.compare(a.getCycle(), b.getCycle());
            }
        });
        return frames;
    }

    private void validateInput(AttentionData.TrialInput input) {
        if (input == null) {
            throw new IllegalArgumentException("TrialInput is null");
        }
        if (input.targetNormalized == null) {
            throw new IllegalArgumentException("TrialInput.targetNormalized is required");
        }
        if (input.targetOnsetCycle == null) {
            throw new IllegalArgumentException("TrialInput.targetOnsetCycle is required");
        }
        if (input.frames == null || input.frames.isEmpty()) {
            throw new IllegalArgumentException("TrialInput.frames is empty");
        }
        if (input.trialType == null || input.trialType == AttentionData.TrialType.UNDEFINED) {
            throw new IllegalArgumentException("TrialInput.trialType must be defined by the benchmark controller");
        }
    }

    private Long resolveDetectionCycle(AttentionData.TrialInput input, List<AttentionData.Frame> frames) {
        if (input.externalDetectionCycle != null) {
            if (input.externalDetectionCycle.longValue() >= input.targetOnsetCycle.longValue()) {
                return input.externalDetectionCycle;
            }
            return null;
        }

        return detectFirstCycleAfterTargetOnset(frames, input);
    }

    private Long detectFirstCycleAfterTargetOnset(List<AttentionData.Frame> frames, AttentionData.TrialInput input) {
        for (AttentionData.Frame frame : frames) {
            if (frame.getCycle() < input.targetOnsetCycle.longValue()) {
                continue;
            }

            if (isNeutralFrame(frame)) {
                continue;
            }

            AttentionData.Point peak = frame.getPeakNormalized();
            if (distance(peak, input.targetNormalized) <= input.targetRadiusNormalized) {
                return frame.getCycle();
            }

            if (config.detectionThreshold != null) {
                double vAtTarget = frame.getValueAtNormalized(input.targetNormalized);
                if (vAtTarget >= config.detectionThreshold.doubleValue()) {
                    return frame.getCycle();
                }
            }
        }

        return null;
    }

    private AttentionData.Frame chooseInitialFrame(AttentionData.TrialInput input, List<AttentionData.Frame> frames) {
        Long reference = input.cueOnsetCycle != null ? input.cueOnsetCycle : input.targetOnsetCycle;
        AttentionData.Frame best = frames.get(0);

        for (AttentionData.Frame frame : frames) {
            if (frame.getCycle() <= reference.longValue()) {
                best = frame;
            } else {
                break;
            }
        }

        return best;
    }

    private AttentionData.Frame chooseReferenceFrame(List<AttentionData.Frame> frames, Long detectionCycle) {
        if (!config.useDetectionFrameAsReference || detectionCycle == null) {
            return frames.get(frames.size() - 1);
        }

        AttentionData.Frame best = frames.get(0);

        for (AttentionData.Frame frame : frames) {
            if (frame.getCycle() <= detectionCycle.longValue()) {
                best = frame;
            } else {
                break;
            }
        }

        return best;
    }

    private Long firstBiasCycle(
            List<AttentionData.Frame> frames,
            AttentionData.Point pointOfInterest,
            AttentionData.Point baselinePoint,
            Long startCycle
    ) {
        if (pointOfInterest == null || baselinePoint == null) return null;

        long start = startCycle == null ? Long.MIN_VALUE : startCycle.longValue();

        for (AttentionData.Frame frame : frames) {
            if (frame.getCycle() < start) continue;
            if (isNeutralFrame(frame)) continue;

            double interest = frame.getValueAtNormalized(pointOfInterest);
            double baseline = frame.getValueAtNormalized(baselinePoint);
            AttentionData.Point peak = frame.getPeakNormalized();

            if ((interest - baseline) > config.attentionBiasThreshold
                    || distance(peak, pointOfInterest) <= config.matchToleranceNormalized) {
                return frame.getCycle();
            }
        }

        return null;
    }

    private boolean isNeutralFrame(AttentionData.Frame frame) {
        if (frame == null) return false;

        boolean neutralByEntropy = false;
        boolean neutralByVariance = false;

        if (isFinite(config.neutralEntropyMin) && config.neutralEntropyMin > 0.0) {
            double e = frame.normalizedEntropy();
            neutralByEntropy = isFinite(e) && e >= config.neutralEntropyMin;
        }

        if (isFinite(config.neutralVarianceThreshold) && config.neutralVarianceThreshold >= 0.0) {
            double v = frame.variance();
            neutralByVariance = isFinite(v) && v <= config.neutralVarianceThreshold;
        }

        return neutralByEntropy || neutralByVariance;
    }

    private Double computeReactionTime(AttentionData.TrialInput input, Long detectionCycle) {
        if (detectionCycle == null || input.targetOnsetCycle == null) {
            return null;
        }
        if (detectionCycle.longValue() < input.targetOnsetCycle.longValue()) {
            return null;
        }
        return (double) (detectionCycle.longValue() - input.targetOnsetCycle.longValue());
    }

    private double fidelity(AttentionData.Frame frame, AttentionData.Point target) {
        if (frame == null || target == null) return Double.NaN;

        AttentionData.Point peak = frame.getPeakNormalized();
        double d = distance(peak, target);
        double maxDistance = Math.sqrt(2.0);
        double f = 1.0 - (d / maxDistance);

        if (f < 0.0) f = 0.0;
        if (f > 1.0) f = 1.0;

        return f;
    }

    private double distance(AttentionData.Point a, AttentionData.Point b) {
        double dx = a.getX() - b.getX();
        double dy = a.getY() - b.getY();
        return Math.sqrt((dx * dx) + (dy * dy));
    }

    private double meanReactionTime(List<AttentionEvaluationReport.TrialResult> results, AttentionData.TrialType type) {
        List<Double> values = new ArrayList<Double>();

        for (AttentionEvaluationReport.TrialResult r : results) {
            if (r.trialType == type
                    && r.reactionTimeCycles != null
                    && isFinite(r.reactionTimeCycles.doubleValue())) {
                values.add(r.reactionTimeCycles);
            }
        }

        return mean(values);
    }

    private double meanInitialFidelity(List<AttentionEvaluationReport.TrialResult> results, AttentionData.TrialType type) {
        List<Double> values = new ArrayList<Double>();

        for (AttentionEvaluationReport.TrialResult r : results) {
            if (type == null || r.trialType == type) {
                if (isFinite(r.initialFidelity)) values.add(r.initialFidelity);
            }
        }

        return mean(values);
    }

    private double meanFinalFidelity(List<AttentionEvaluationReport.TrialResult> results, AttentionData.TrialType type) {
        List<Double> values = new ArrayList<Double>();

        for (AttentionEvaluationReport.TrialResult r : results) {
            if (type == null || r.trialType == type) {
                if (isFinite(r.finalFidelity)) values.add(r.finalFidelity);
            }
        }

        return mean(values);
    }

    private double meanRt(List<AttentionEvaluationReport.TrialResult> results) {
        List<Double> values = new ArrayList<Double>();

        for (AttentionEvaluationReport.TrialResult r : results) {
            if (r.reactionTimeCycles != null && isFinite(r.reactionTimeCycles.doubleValue())) {
                values.add(r.reactionTimeCycles);
            }
        }

        return mean(values);
    }

    private double meanRtFlanked(
            List<AttentionEvaluationReport.TrialResult> results,
            Boolean flanked,
            AttentionData.TrialType type,
            Double distance
    ) {
        List<Double> values = new ArrayList<Double>();

        for (AttentionEvaluationReport.TrialResult r : results) {
            if (flanked != null && !flanked.equals(r.flanked)) continue;
            if (type != null && r.trialType != type) continue;

            if (distance != null) {
                if (r.flankerDistance == null) continue;
                if (Math.abs(r.flankerDistance.doubleValue() - distance.doubleValue()) > 1e-9) continue;
            }

            if (r.reactionTimeCycles != null && isFinite(r.reactionTimeCycles.doubleValue())) {
                values.add(r.reactionTimeCycles);
            }
        }

        return mean(values);
    }

    private Double nullableMean(List<Double> values) {
        double m = mean(values);
        return isFinite(m) ? Double.valueOf(m) : null;
    }

    private double mean(List<Double> values) {
        if (values == null || values.isEmpty()) return Double.NaN;

        double sum = 0.0;
        int n = 0;

        for (Double v : values) {
            if (v != null && isFinite(v.doubleValue())) {
                sum += v.doubleValue();
                n++;
            }
        }

        if (n == 0) return Double.NaN;

        return sum / (double) n;
    }

    private Double slopeForSearchType(List<AttentionEvaluationReport.TrialResult> results,
                                      AttentionData.SearchType searchType) {
        TreeMap<Integer, List<Double>> byN = new TreeMap<Integer, List<Double>>();

        for (AttentionEvaluationReport.TrialResult r : results) {
            if (r.searchType != searchType) continue;
            if (r.distractorCount == null) continue;
            if (r.reactionTimeCycles == null || !isFinite(r.reactionTimeCycles.doubleValue())) continue;

            List<Double> values = byN.get(r.distractorCount);
            if (values == null) {
                values = new ArrayList<Double>();
                byN.put(r.distractorCount, values);
            }
            values.add(r.reactionTimeCycles);
        }

        List<Double> xs = new ArrayList<Double>();
        List<Double> ys = new ArrayList<Double>();

        for (Map.Entry<Integer, List<Double>> entry : byN.entrySet()) {
            double y = mean(entry.getValue());
            if (isFinite(y)) {
                xs.add(entry.getKey().doubleValue());
                ys.add(y);
            }
        }

        double slope = linearSlope(xs, ys);
        return isFinite(slope) ? Double.valueOf(slope) : null;
    }

    private double linearSlope(List<Double> xs, List<Double> ys) {
        if (xs == null || ys == null || xs.size() != ys.size() || xs.size() < 2) {
            return Double.NaN;
        }

        double sumX = 0.0;
        double sumY = 0.0;
        double sumXX = 0.0;
        double sumXY = 0.0;
        int n = 0;

        for (int i = 0; i < xs.size(); i++) {
            double x = xs.get(i);
            double y = ys.get(i);

            if (!isFinite(x) || !isFinite(y)) continue;

            sumX += x;
            sumY += y;
            sumXX += x * x;
            sumXY += x * y;
            n++;
        }

        if (n < 2) return Double.NaN;

        double denom = (n * sumXX) - (sumX * sumX);
        if (Math.abs(denom) < 1e-12) return Double.NaN;

        return ((n * sumXY) - (sumX * sumY)) / denom;
    }

    private void writePerTrialCsv(AttentionEvaluationReport.Summary summary) throws IOException {
        File file = new File(
                config.outDir,
                safeName(config.filePrefix)
                    + "_exp"
                    + summary.posnerExperimentId
                    + "_"
                    + safeName(summary.experimentId)
                    + "_per_trial_episode_"
                    + summary.episode
                    + "_"
                    + safeName(summary.architectureName)
                    + ".csv"
        );

        
        System.out.print("writePerTrialCsv printed on: "+config.outDir);
        PrintWriter pw = new PrintWriter(new FileWriter(file, false));

        try {
            pw.println("posner_experiment_id,experiment_id,architecture,episode,trial_id,modality,cue_type,trial_type,search_type,distractor_count,flanked,flanker_distance,cue_onset_cycle,target_onset_cycle,detection_cycle,overt_movement_cycle,reaction_time_cycles,soa_ms,attention_latency_cycles,bottom_up_latency_cycles,eye_movement_latency_cycles,target_x,target_y,cue_x,cue_y,fixation_x,fixation_y,focus_x,focus_y,peak_value,map_variance,normalized_entropy,initial_fidelity,final_fidelity");

            for (AttentionEvaluationReport.TrialResult r : summary.trials) {
                pw.printf(
                        Locale.US,
                        "%d,%s,%s,%d,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%.10f,%.10f,%s,%s,%s,%s,%.10f,%.10f,%.10f,%.10f,%.10f,%.10f,%.10f%n",
                        summary.posnerExperimentId,
                        csv(summary.experimentId),
                        csv(summary.architectureName),
                        summary.episode,
                        csv(r.trialId),
                        csv(r.modality),
                        r.cueType.name(),
                        r.trialType.name(),
                        r.searchType.name(),
                        nullableInteger(r.distractorCount),
                        nullableBoolean(r.flanked),
                        nullableDouble(r.flankerDistance),
                        nullableLong(r.cueOnsetCycle),
                        nullableLong(r.targetOnsetCycle),
                        nullableLong(r.detectionCycle),
                        nullableLong(r.overtMovementCycle),
                        nullableDouble(r.reactionTimeCycles),
                        nullableDouble(r.soaMs),
                        nullableDouble(r.attentionLatencyCycles),
                        nullableDouble(r.bottomUpLatencyCycles),
                        nullableDouble(r.eyeMovementLatencyCycles),
                        r.targetX,
                        r.targetY,
                        nullableDoubleValue(r.cueX),
                        nullableDoubleValue(r.cueY),
                        nullableDoubleValue(r.fixationX),
                        nullableDoubleValue(r.fixationY),
                        r.focusX,
                        r.focusY,
                        r.peakValue,
                        r.mapVariance,
                        r.normalizedEntropy,
                        r.initialFidelity,
                        r.finalFidelity
                );
            }
        } finally {
            pw.flush();
            pw.close();
        }
        printSavedFile(file);
    }

    private void writeSummaryCsv(AttentionEvaluationReport.Summary summary) throws IOException {
        File file = new File(
                config.outDir,
                safeName(config.filePrefix)
                + "_exp"
                + summary.posnerExperimentId
                + "_"
                + safeName(summary.experimentId)
                + "_summary_episode_"
                + summary.episode
                + "_"
                + safeName(summary.architectureName)
                + ".csv"
        );

        PrintWriter pw = new PrintWriter(new FileWriter(file, false));
        System.out.print("writeSummaryCsv printed on: "+config.outDir);
        try {
            pw.println("posner_experiment_id,experiment_id,architecture,episode,aborted,total_trials,mean_rt_valid,mean_rt_invalid,mean_rt_neutral,benefit,cost,validity_effect,mean_initial_fidelity_overall,mean_final_fidelity_overall,mean_final_fidelity_valid,mean_final_fidelity_invalid,mean_final_fidelity_neutral,top_down_orienting_latency,mean_bottom_up_latency,mean_eye_movement_latency,mean_rt_cued,mean_rt_uncued,feature_search_slope,conjunction_search_slope");

            pw.printf(
                    Locale.US,
                    "%d,%s,%s,%d,%s,%d,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s%n",
                    summary.posnerExperimentId,
                    csv(summary.experimentId),
                    csv(summary.architectureName),
                    summary.episode,
                    Boolean.toString(summary.aborted),
                    summary.totalTrials,
                    nullableDoubleValue(summary.meanRtValid),
                    nullableDoubleValue(summary.meanRtInvalid),
                    nullableDoubleValue(summary.meanRtNeutral),
                    nullableDoubleValue(summary.benefit),
                    nullableDoubleValue(summary.cost),
                    nullableDoubleValue(summary.validityEffect),
                    nullableDoubleValue(summary.meanInitialFidelityOverall),
                    nullableDoubleValue(summary.meanFinalFidelityOverall),
                    nullableDoubleValue(summary.meanFinalFidelityValid),
                    nullableDoubleValue(summary.meanFinalFidelityInvalid),
                    nullableDoubleValue(summary.meanFinalFidelityNeutral),
                    nullableDouble(summary.topDownOrientingLatency),
                    nullableDouble(summary.meanBottomUpLatency),
                    nullableDouble(summary.meanEyeMovementLatency),
                    nullableDouble(summary.meanRtCued),
                    nullableDouble(summary.meanRtUncued),
                    nullableDouble(summary.featureSearchSlope),
                    nullableDouble(summary.conjunctionSearchSlope)
            );
        } finally {
            pw.flush();
            pw.close();
        }
        printSavedFile(file);
    }

    private void writeSoaCsv(AttentionEvaluationReport.Summary summary) throws IOException {
        if (summary.soaValues.isEmpty()) return;

        File file = new File(
                config.outDir,
                safeName(config.filePrefix)
                + "_exp"
                + summary.posnerExperimentId
                + "_"
                + safeName(summary.experimentId)
                + "_soa_episode_"
                + summary.episode
                + "_"
                + safeName(summary.architectureName)
                + ".csv"
        );

        PrintWriter pw = new PrintWriter(new FileWriter(file, false));
        System.out.print("writeSoaCsv printed on: "+config.outDir);
        try {
            pw.println("posner_experiment_id,experiment_id,architecture,episode,soa_ms,benefit,cost");

            for (int i = 0; i < summary.soaValues.size(); i++) {
                pw.printf(
                        Locale.US,
                        "%d,%s,%s,%d,%s,%s,%s%n",
                        summary.posnerExperimentId,
                        csv(summary.experimentId),
                        csv(summary.architectureName),
                        summary.episode,
                        nullableDoubleValue(summary.soaValues.get(i)),
                        nullableDoubleValue(summary.benefitBySoa.get(i)),
                        nullableDoubleValue(summary.costBySoa.get(i))
                );
            }
        } finally {
            pw.flush();
            pw.close();
        }
        printSavedFile(file);
    }

    private void writeCrowdingCsv(AttentionEvaluationReport.Summary summary) throws IOException {
        if (summary.flankerDistances.isEmpty()) return;
        System.out.print("writeCrowdingCsv printed on: "+config.outDir);
        File file = new File(
                config.outDir,
                safeName(config.filePrefix)
                + "_exp"
                + summary.posnerExperimentId
                + "_"
                + safeName(summary.experimentId)
                + "_crowding_episode_"
                + summary.episode
                + "_"
                + safeName(summary.architectureName)
                + ".csv"
        );

        PrintWriter pw = new PrintWriter(new FileWriter(file, false));

        try {
            pw.println("posner_experiment_id,experiment_id,architecture,episode,flanker_distance,crowding_cost,attentional_reduction_crowding");

            for (int i = 0; i < summary.flankerDistances.size(); i++) {
                pw.printf(
                        Locale.US,
                        "%d,%s,%s,%d,%s,%s,%s%n",
                        summary.posnerExperimentId,
                        csv(summary.experimentId),
                        csv(summary.architectureName),
                        summary.episode,
                        nullableDoubleValue(summary.flankerDistances.get(i)),
                        nullableDoubleValue(summary.crowdingCostByDistance.get(i)),
                        nullableDoubleValue(summary.attentionalReductionByDistance.get(i))
                );
            }
        } finally {
            pw.flush();
            pw.close();
        }
        printSavedFile(file);
    }

    private void validateExperimentId(int id) {
        if (id < EXP1_CENTRAL_CUE || id > EXP5_CROWDING) {
            throw new IllegalArgumentException("Posner experiment id must be between 1 and 5. Received: " + id);
        }
    }

    private String experimentName(int id) {
        switch (id) {
            case EXP1_CENTRAL_CUE:
                return "exp1_central_cue_posner";
            case EXP2_SOA_SWEEP:
                return "exp2_soa_sweep";
            case EXP3_PERIPHERAL_CAPTURE:
                return "exp3_peripheral_capture";
            case EXP4_VISUAL_SEARCH:
                return "exp4_visual_search";
            case EXP5_CROWDING:
                return "exp5_crowding";
            default:
                return "attention_experiment";
        }
    }

    private boolean isFinite(double v) {
        return !Double.isNaN(v) && !Double.isInfinite(v);
    }

    private String safeTrialId(String trialId, AttentionData.TrialInput input, List<AttentionData.Frame> frames) {
        if (trialId != null && !trialId.trim().isEmpty()) {
            return trialId;
        }

        long first = frames.get(0).getCycle();
        long last = frames.get(frames.size() - 1).getCycle();

        return "trial_ep" + input.episode + "_c" + first + "_to_" + last + "_n" + frames.size();
    }

    private String blankToDefault(String s, String fallback) {
        if (s == null || s.trim().isEmpty()) return fallback;
        return s;
    }

    private String safeName(String s) {
        if (s == null || s.trim().isEmpty()) return "unknown";
        return s.replaceAll("[^a-zA-Z0-9_\\-\\.]", "_");
    }

    private String csv(String s) {
        if (s == null) return "";
        return s.replace(",", "_").replace("\n", " ").replace("\r", " ");
    }

    private String nullableLong(Long v) {
        return v == null ? "" : Long.toString(v.longValue());
    }

    private String nullableInteger(Integer v) {
        return v == null ? "" : Integer.toString(v.intValue());
    }

    private String nullableBoolean(Boolean v) {
        return v == null ? "" : Boolean.toString(v.booleanValue());
    }

    private String nullableDouble(Double v) {
        return v == null ? "" : nullableDoubleValue(v.doubleValue());
    }

    private String nullableDoubleValue(Double v) {
        return v == null ? "" : nullableDoubleValue(v.doubleValue());
    }

    private String nullableDoubleValue(double v) {
        if (!isFinite(v)) return "";
        return String.format(Locale.US, "%.10f", v);
    }
}