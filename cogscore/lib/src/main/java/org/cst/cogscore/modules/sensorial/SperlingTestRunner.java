/*
 * Click nbfs://nbhost/SystemFileSystem/Templates/Licenses/license-default.txt to change this license
 * Click nbfs://nbhost/SystemFileSystem/Templates/Classes/Class.java to edit this template
 */
package org.modules.sensorial;

/**
 *
 * @author leolellisr
 */
// modules/sensorial/SperlingTestRunner.java

import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import java.util.function.Supplier;

/**
 * Runner for Sperling-inspired partial-report buffer fidelity tests.
 *
 * The runner is designed as a library component:
 * it does NOT assume any specific architecture implementation (CST or otherwise).
 * Integration happens through BufferAccessor and TrialHooks.
 *
 * Key design goal:
 * - If the underlying buffer cannot be truly locked, the provided FunctionalBufferAccessor
 *   can "freeze" the buffer by deep copying the content at lock() time.
 */
public final class SperlingTestRunner {

    private SperlingTestRunner() { }

    /**
     * Abstraction over an agent buffer. Implement this with CST MemoryObjects, or use
     * FunctionalBufferAccessor to wrap a Supplier<T>.
     */
    public interface BufferAccessor<T> {
        T read();
        void lock();
        void unlock();
        long lastWriteTimeMillis();
        String debugName();
    }

    /**
     * Provides the ground-truth representation at time t0.
     * This typically reads directly from the environment/simulator, not from the agent.
     */
    public interface GroundTruthProvider<T> {
        T capture();
        String debugName();
    }

    /**
     * Hooks to interact with the agent/environment without forcing any dependency.
     * Most systems already have a loop; these hooks let you insert the test in that loop.
     */
    public interface TrialHooks {
        /**
         * Called right before acquiring t0 data.
         * Typical usage: configure environment to S(t0), reset distractors, etc.
         */
        void beforeStimulus(int trialIndex, long delayMs);

        /**
         * Called to ensure the agent performs sensing and writes into its buffers.
         * Typical usage: run one cycle, or trigger perception codelets.
         */
        void triggerSensing(int trialIndex, long delayMs);

        /**
         * Called immediately after t0 was acquired and buffer was locked (frozen).
         * Typical usage: change environment to S(t1) to prevent re-sensing of S(t0).
         */
        void afterStimulus(int trialIndex, long delayMs);

        /**
         * Called after finishing a trial.
         * Typical usage: reset agent/environment state for the next trial.
         */
        void afterTrial(int trialIndex, long delayMs);
    }

    /**
     * Default no-op hooks for cases where the test harness controls the environment elsewhere.
     */
    public static TrialHooks noopHooks() {
        return new TrialHooks() {
            @Override public void beforeStimulus(int trialIndex, long delayMs) { }
            @Override public void triggerSensing(int trialIndex, long delayMs) { }
            @Override public void afterStimulus(int trialIndex, long delayMs) { }
            @Override public void afterTrial(int trialIndex, long delayMs) { }
        };
    }

    /**
     * Buffer accessor implementation that wraps a Supplier<T>.
     *
     * If freezeOnLock is true, lock() will read the current value, deep copy it,
     * and future reads will return the frozen copy until unlock().
     *
     * This is the simplest way to integrate with CST:
     * - supplier reads memoryObject.getI()
     * - deep copy prevents overwrites from affecting the evaluation
     */
    public static final class FunctionalBufferAccessor<T> implements BufferAccessor<T> {
        private final String name;
        private final Supplier<T> supplier;
        private final boolean freezeOnLock;

        private volatile boolean locked = false;
        private volatile T frozenCopy = null;
        private volatile long lastWriteMillis = -1;

        public FunctionalBufferAccessor(String name, Supplier<T> supplier, boolean freezeOnLock) {
            if (name == null) throw new IllegalArgumentException("name == null");
            if (supplier == null) throw new IllegalArgumentException("supplier == null");
            this.name = name;
            this.supplier = supplier;
            this.freezeOnLock = freezeOnLock;
        }

        @Override
        public T read() {
            if (freezeOnLock && locked) {
                return frozenCopy;
            }
            return supplier.get();
        }

        @Override
        public void lock() {
            locked = true;
            if (freezeOnLock) {
                T current = supplier.get();
                frozenCopy = BufferSnapshot.deepCopy(current);
                lastWriteMillis = System.currentTimeMillis();
            }
        }

        @Override
        public void unlock() {
            locked = false;
            frozenCopy = null;
        }

        @Override
        public long lastWriteTimeMillis() {
            return lastWriteMillis;
        }

        @Override
        public String debugName() {
            return name;
        }
    }

    /**
     * Ground truth provider implementation that wraps a Supplier<T>.
     */
    public static final class FunctionalGroundTruthProvider<T> implements GroundTruthProvider<T> {
        private final String name;
        private final Supplier<T> supplier;

        public FunctionalGroundTruthProvider(String name, Supplier<T> supplier) {
            if (name == null) throw new IllegalArgumentException("name == null");
            if (supplier == null) throw new IllegalArgumentException("supplier == null");
            this.name = name;
            this.supplier = supplier;
        }

        @Override
        public T capture() {
            return supplier.get();
        }

        @Override
        public String debugName() {
            return name;
        }
    }

    /**
     * Test plan for a single modality.
     */
    public static final class ModalityPlan<T> {
        public final String agentId;
        public final String modality;

        public final BufferAccessor<T> buffer;
        public final GroundTruthProvider<T> groundTruth;

        public final CueGenerator.Generator<T> cueGenerator;
        public final FidelityMetric.Metric<T> metric;

        public final long stimulusMs;
        public final long[] delaysMs;
        public final int trialsPerDelay;

        public final TrialHooks hooks;

        public ModalityPlan(
                String agentId,
                String modality,
                BufferAccessor<T> buffer,
                GroundTruthProvider<T> groundTruth,
                CueGenerator.Generator<T> cueGenerator,
                FidelityMetric.Metric<T> metric,
                long stimulusMs,
                long[] delaysMs,
                int trialsPerDelay,
                TrialHooks hooks
        ) {
            if (agentId == null) throw new IllegalArgumentException("agentId == null");
            if (modality == null) throw new IllegalArgumentException("modality == null");
            if (buffer == null) throw new IllegalArgumentException("buffer == null");
            if (groundTruth == null) throw new IllegalArgumentException("groundTruth == null");
            if (cueGenerator == null) throw new IllegalArgumentException("cueGenerator == null");
            if (metric == null) throw new IllegalArgumentException("metric == null");
            if (delaysMs == null || delaysMs.length == 0) throw new IllegalArgumentException("delaysMs must not be empty");
            if (trialsPerDelay <= 0) throw new IllegalArgumentException("trialsPerDelay must be > 0");
            if (stimulusMs < 0) throw new IllegalArgumentException("stimulusMs must be >= 0");
            this.agentId = agentId;
            this.modality = modality;
            this.buffer = buffer;
            this.groundTruth = groundTruth;
            this.cueGenerator = cueGenerator;
            this.metric = metric;
            this.stimulusMs = stimulusMs;
            this.delaysMs = delaysMs.clone();
            this.trialsPerDelay = trialsPerDelay;
            this.hooks = (hooks == null) ? noopHooks() : hooks;
        }
    }

    /**
     * Runs one modality plan and returns a modality report.
     */
    public static <T> EvaluationReport.ModalityReport runModality(ModalityPlan<T> plan, Random rnd) {
        if (rnd == null) rnd = new Random();

        int K = plan.delaysMs.length;
        int R = plan.trialsPerDelay;

        double[][] fidelity = new double[K][R];
        double[][] distance = new double[K][R];
        String[][] cueDesc = new String[K][R];

        for (int k = 0; k < K; k++) {
            long delayMs = plan.delaysMs[k];

            for (int r = 0; r < R; r++) {
                plan.hooks.beforeStimulus(r, delayMs);

                // Ensure the agent senses and writes to its buffers.
                plan.hooks.triggerSensing(r, delayMs);

                // Optional stimulus duration (if you want to hold the state stable).
                if (plan.stimulusMs > 0) {
                    sleepSilently(plan.stimulusMs);
                }

                // Capture ground truth at t0 (external, not from the agent).
                long t0 = System.currentTimeMillis();
                T gt = BufferSnapshot.deepCopy(plan.groundTruth.capture());
                BufferSnapshot<T> snapshot = new BufferSnapshot<>(plan.modality, t0, gt);

                // Freeze/lock the agent buffer so later reads correspond to t0.
                plan.buffer.lock();

                // Change environment to S(t1) (prevent re-sensing of S(t0)).
                plan.hooks.afterStimulus(r, delayMs);

                // Retention interval.
                if (delayMs > 0) {
                    sleepSilently(delayMs);
                }

                // Generate and apply the same cue to both buffer and ground truth.
                CueGenerator.Cue<T> cue = plan.cueGenerator.sample(rnd, snapshot.getGroundTruth());
                String cdesc = cue.describe();

                T storedFull = plan.buffer.read();
                T storedSubset = cue.extract(storedFull);
                T truthSubset = cue.extract(snapshot.getGroundTruth());

                double d = plan.metric.distance(storedSubset, truthSubset);
                double f = 1.0 - (d / plan.metric.maxDistance());

                // Clamp fidelity for numerical stability.
                if (Double.isFinite(f)) {
                    if (f < 0) f = 0;
                    if (f > 1) f = 1;
                }

                fidelity[k][r] = f;
                distance[k][r] = d;
                cueDesc[k][r] = cdesc;

                plan.buffer.unlock();
                plan.hooks.afterTrial(r, delayMs);
            }
        }

        EvaluationReport.ModalityReport mr = new EvaluationReport.ModalityReport(
                plan.agentId,
                plan.modality,
                plan.metric.name(),
                plan.cueGenerator.name(),
                plan.delaysMs,
                fidelity,
                distance,
                cueDesc
        );

        // Compute summary stats and fit decay model.
        mr.computeSummaries();
        mr.decay = DecayModelFitter.fitExponential(plan.delaysMs, mr.meanFidelity);

        return mr;
    }

    /**
     * Runs multiple modality plans and returns a full report.
     */
    public static EvaluationReport runAll(List<ModalityPlan<?>> plans, long randomSeed) {
        if (plans == null || plans.isEmpty()) throw new IllegalArgumentException("plans must not be empty");
        Random rnd = new Random(randomSeed);

        List<EvaluationReport.ModalityReport> reports = new ArrayList<>();
        for (ModalityPlan<?> p : plans) {
            reports.add(runModalityUnchecked(p, rnd));
        }
        return new EvaluationReport(reports);
    }

    @SuppressWarnings({"rawtypes", "unchecked"})
    private static EvaluationReport.ModalityReport runModalityUnchecked(ModalityPlan plan, Random rnd) {
        return runModality(plan, rnd);
    }

    private static void sleepSilently(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException ie) {
            Thread.currentThread().interrupt();
        }
    }
}