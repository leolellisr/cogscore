package codelets.sensors;

import CommunicationInterface.SensorI;
import br.unicamp.cst.core.entities.Codelet;
import org.cst.cogscore.modules.sensory.remote.RemoteSensoryClient;

import java.io.File;
import java.io.FileWriter;
import java.io.PrintWriter;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import java.util.Objects;
import java.util.Random;

public class RGBSperlingRemoteBridge extends Codelet {

    private final SensorI visionSensor;
    private final RemoteSensoryClient remoteClient;

    private final int res;
    private final int patchSize;
    private final long[] delaysMs;
    private final int trialsPerDelay;
    private final long freshFrameTimeoutMs;
    private final File outDir;
    private final Random rnd;

    private Phase phase = Phase.WAIT_EPISODE_START;

    private int currentEpisode = -1;
    private int delayIdx = 0;
    private int trialIdx = 0;
    private int warmupFreshFrames = 0;

    private long retentionEndMs = 0;

    private List<Float> groundTruthT0 = null;
    private PatchCue cue = null;

    private final double[] sumF;
    private final double[] sumF2;
    private final int[] count;

    private PrintWriter perTrialWriter = null;

    private enum Phase {
        WAIT_EPISODE_START,
        WARMUP,
        CAPTURE_T0,
        RETENTION,
        QUERY_REMOTE_AND_LOG,
        FINISH_EPISODE
    }

    private static class PatchCue {
        final int x0;
        final int y0;
        final int size;

        PatchCue(int x0, int y0, int size) {
            this.x0 = x0;
            this.y0 = y0;
            this.size = size;
        }

        String describe() {
            return "VisionPatchList[x0=" + x0 + ",y0=" + y0 + ",s=" + size + "]";
        }
    }

    public RGBSperlingRemoteBridge(
            SensorI visionSensor,
            String remoteArchitectureUrl,
            int res,
            int patchSize,
            long[] delaysMs,
            int trialsPerDelay,
            long freshFrameTimeoutMs,
            File outDir,
            long seed
    ) {
        this.visionSensor = Objects.requireNonNull(visionSensor, "visionSensor");
        this.remoteClient = new RemoteSensoryClient(remoteArchitectureUrl);
        this.res = res;
        this.patchSize = patchSize;
        this.delaysMs = Arrays.copyOf(delaysMs, delaysMs.length);
        this.trialsPerDelay = trialsPerDelay;
        this.freshFrameTimeoutMs = Math.max(50, freshFrameTimeoutMs);
        this.outDir = outDir == null ? new File("vision_sperling_remote_out") : outDir;
        this.rnd = new Random(seed);

        if (!this.outDir.exists()) {
            this.outDir.mkdirs();
        }

        this.sumF = new double[delaysMs.length];
        this.sumF2 = new double[delaysMs.length];
        this.count = new int[delaysMs.length];

        setTimeStep(20);
    }

    @Override
    public void accessMemoryObjects() {
    }

    @Override
    public void calculateActivation() {
    }

    @Override
    public void proc() {
        int episode = visionSensor.getEpoch();

        if (currentEpisode < 0) {
            startEpisode(episode);
        } else if (episode != currentEpisode) {
            finishEpisode(currentEpisode, true);
            startEpisode(episode);
        }

        switch (phase) {
            case WAIT_EPISODE_START:
                break;

            case WARMUP:
                List<Float> fresh = snapshotFreshFromSensor(freshFrameTimeoutMs);
                if (fresh != null) {
                    warmupFreshFrames++;
                }

                if (warmupFreshFrames >= 2) {
                    warmupFreshFrames = 0;
                    phase = Phase.CAPTURE_T0;
                }
                break;

            case CAPTURE_T0:
                groundTruthT0 = snapshotFreshFromSensor(freshFrameTimeoutMs);

                if (groundTruthT0 == null) {
                    break;
                }

                cue = samplePatchCue();

                try {
                    remoteClient.sendStimulus(
                            currentEpisode,
                            trialIdx,
                            delaysMs[delayIdx],
                            res,
                            res,
                            groundTruthT0
                    );
                } catch (Exception exc) {
                    System.err.println("[RGBSperlingRemoteBridge] sendStimulus failed: " + exc.getMessage());
                    break;
                }

                retentionEndMs = System.currentTimeMillis() + delaysMs[delayIdx];
                phase = Phase.RETENTION;
                break;

            case RETENTION:
                if (System.currentTimeMillis() >= retentionEndMs) {
                    phase = Phase.QUERY_REMOTE_AND_LOG;
                }
                break;

            case QUERY_REMOTE_AND_LOG:
                try {
                    List<Float> truthPatch = extractPatch(groundTruthT0, cue);
                    List<Float> storedPatch = remoteClient.readoutPatch(
                            currentEpisode,
                            trialIdx,
                            delaysMs[delayIdx],
                            cue.x0,
                            cue.y0,
                            cue.size
                    );

                    double distance = mse(storedPatch, truthPatch);
                    double fidelity = 1.0 - distance / (255.0 * 255.0);

                    if (Double.isFinite(fidelity)) {
                        fidelity = Math.max(0.0, Math.min(1.0, fidelity));
                    } else {
                        fidelity = 0.0;
                    }

                    writePerTrial(
                            currentEpisode,
                            delaysMs[delayIdx],
                            trialIdx,
                            cue.describe(),
                            distance,
                            fidelity
                    );

                    sumF[delayIdx] += fidelity;
                    sumF2[delayIdx] += fidelity * fidelity;
                    count[delayIdx]++;

                    advanceScheduleOrFinish();

                } catch (Exception exc) {
                    System.err.println("[RGBSperlingRemoteBridge] readout failed: " + exc.getMessage());
                }
                break;

            case FINISH_EPISODE:
                break;
        }
    }

    private void startEpisode(int episode) {
        currentEpisode = episode;
        delayIdx = 0;
        trialIdx = 0;
        warmupFreshFrames = 0;

        Arrays.fill(sumF, 0.0);
        Arrays.fill(sumF2, 0.0);
        Arrays.fill(count, 0);

        openPerTrial(episode);

        try {
            remoteClient.health();
            remoteClient.reset(episode);
        } catch (Exception exc) {
            System.err.println("[RGBSperlingRemoteBridge] remote reset failed: " + exc.getMessage());
        }

        phase = Phase.WARMUP;

        System.out.println("[RGBSperlingRemoteBridge] episode started: episode=" + episode);
    }

    private void advanceScheduleOrFinish() {
        trialIdx++;

        if (trialIdx >= trialsPerDelay) {
            trialIdx = 0;
            delayIdx++;
        }

        if (delayIdx >= delaysMs.length) {
            finishEpisode(currentEpisode, false);
            phase = Phase.FINISH_EPISODE;
        } else {
            phase = Phase.CAPTURE_T0;
        }
    }

    private void finishEpisode(int episode, boolean aborted) {
        try {
            closePerTrial();
            writeSummary(episode, aborted);
            remoteClient.close();

            System.out.println("[RGBSperlingRemoteBridge] episode finished: episode=" + episode + " aborted=" + aborted);

        } catch (Exception exc) {
            System.err.println("[RGBSperlingRemoteBridge] finishEpisode failed: " + exc.getMessage());
        }
    }

    private PatchCue samplePatchCue() {
        int x0 = rnd.nextInt(res - patchSize + 1);
        int y0 = rnd.nextInt(res - patchSize + 1);
        return new PatchCue(x0, y0, patchSize);
    }

    private List<Float> snapshotFreshFromSensor(long timeoutMs) {
        long deadline = System.currentTimeMillis() + timeoutMs;

        while (System.currentTimeMillis() < deadline) {
            Object data = visionSensor.getData();

            if (data instanceof List<?>) {
                List<?> raw = (List<?>) data;
                if (raw.size() >= res * res * 3) {
                    ArrayList<Float> out = new ArrayList<>(raw.size());

                    for (Object item : raw) {
                        if (item instanceof Number) {
                            out.add(((Number) item).floatValue());
                        } else {
                            out.add(0.0f);
                        }
                    }

                    return out;
                }
            }

            try {
                Thread.sleep(5);
            } catch (InterruptedException exc) {
                Thread.currentThread().interrupt();
                return null;
            }
        }

        return null;
    }

    private List<Float> extractPatch(List<Float> frame, PatchCue cue) {
        ArrayList<Float> patch = new ArrayList<>(cue.size * cue.size * 3);

        for (int y = cue.y0; y < cue.y0 + cue.size; y++) {
            for (int x = cue.x0; x < cue.x0 + cue.size; x++) {
                int idx = (y * res + x) * 3;
                patch.add(frame.get(idx));
                patch.add(frame.get(idx + 1));
                patch.add(frame.get(idx + 2));
            }
        }

        return patch;
    }

    private double mse(List<Float> a, List<Float> b) {
        int n = Math.min(a.size(), b.size());

        if (n <= 0) {
            return 255.0 * 255.0;
        }

        double sum = 0.0;

        for (int i = 0; i < n; i++) {
            double d = a.get(i) - b.get(i);
            sum += d * d;
        }

        return sum / (double) n;
    }

    private void openPerTrial(int episode) {
        try {
            File f = new File(outDir, "vision_sperling_per_trial_episode_" + episode + "_remote.csv");
            perTrialWriter = new PrintWriter(new FileWriter(f, false));
            perTrialWriter.println("episode,condition,delay_ms,trial_idx,cue_desc,distance_mse,fidelity");
            perTrialWriter.flush();
        } catch (Exception exc) {
            throw new RuntimeException(exc);
        }
    }

    private void closePerTrial() {
        if (perTrialWriter != null) {
            perTrialWriter.flush();
            perTrialWriter.close();
            perTrialWriter = null;
        }
    }

    private void writePerTrial(
            int episode,
            long delayMs,
            int trialIdx,
            String cueDesc,
            double distance,
            double fidelity
    ) {
        if (perTrialWriter == null) {
            return;
        }

        perTrialWriter.printf(
                Locale.US,
                "%d,%s,%d,%d,\"%s\",%.10f,%.10f%n",
                episode,
                "remote",
                delayMs,
                trialIdx,
                cueDesc,
                distance,
                fidelity
        );

        perTrialWriter.flush();
    }

    private void writeSummary(int episode, boolean aborted) throws Exception {
        File f = new File(outDir, "vision_sperling_summary_episode_" + episode + "_remote.csv");

        try (PrintWriter pw = new PrintWriter(new FileWriter(f, false))) {
            pw.println("episode,condition,aborted,delay_ms,mean_fidelity,std_fidelity,F0,lambda,r2,used_points");

            for (int k = 0; k < delaysMs.length; k++) {
                double mean;
                double std;

                if (count[k] == 0) {
                    mean = Double.NaN;
                    std = Double.NaN;
                } else {
                    mean = sumF[k] / count[k];
                    double var = (sumF2[k] / count[k]) - (mean * mean);
                    std = Math.sqrt(Math.max(0.0, var));
                }

                pw.printf(
                        Locale.US,
                        "%d,%s,%s,%d,%.10f,%.10f,%s,%s,%s,%d%n",
                        episode,
                        "remote",
                        Boolean.toString(aborted),
                        delaysMs[k],
                        mean,
                        std,
                        "",
                        "",
                        "",
                        count[k]
                );
            }
        }
    }
}
