#AUTOGENERATED! DO NOT EDIT! File to edit: dev/70_callback_wandb.ipynb (unless otherwise specified).

__all__ = ['WandbCallback', 'wand_process', 'wand_process']

#Cell
from ..test import *
from ..basics import *
from .progress import *

#Cell
import wandb
from .tracker import SaveModelCallback

#Cell
class WandbCallback(Callback):
    "Saves model topology, losses & metrics"
    # Record if watch has been called previously (even in another instance)
    run_after=SaveModelCallback
    _watch_called = False

    def __init__(self, log="gradients", log_preds=True, valid_dl=None, n_preds=36, seed=12345):
        # Check if wandb.init has been called
        if wandb.run is None:
            raise ValueError('You must call wandb.init() before WandbCallback()')
        store_attr(self, 'log,log_preds,valid_dl,n_preds,seed')

    def begin_fit(self):
        "Call watch method to log model topology, gradients & weights"
        if not WandbCallback._watch_called:
            WandbCallback._watch_called = True
            # Logs model topology and optionally gradients and weights
            wandb.watch(self.learn.model, log=self.log)

        if hasattr(self, 'save_model'): self.save_model.add_save = Path(wandb.run.dir)/'bestmodel.pth'

        if self.log_preds and not self.valid_dl:
            #Initializes the batch watched
            wandbRandom = random.Random(self.seed)  # For repeatability
            self.n_preds = min(self.n_preds, len(self.dbunch.valid_ds))
            idxs = wandbRandom.sample(range(len(self.dbunch.valid_ds)), self.n_preds)

            items = [self.dbunch.valid_ds.items[i] for i in idxs]
            test_tls = [tl._new(items, split_idx=1) for tl in self.dbunch.valid_ds.tls]
            self.valid_dl = self.dbunch.valid_dl.new(DataSource(tls=test_tls), bs=self.n_preds)

    def after_batch(self):
        hypers = {f'{k}_{i}':v for i,h in enumerate(self.opt.hypers) for k,v in h.items()}
        wandb.log({'train_loss': self.smooth_loss, **hypers})

    def after_epoch(self):
        "Log training loss, validation loss and custom metrics & log prediction samples & save model"
        # Log sample predictions
        if self.log_preds is not None:
            b = self.valid_dl.one_batch()
            self.learn.one_batch(0, b)
            preds = getattr(self.loss_func, 'activation', noop)(self.pred)
            out = getattr(self.loss_func, 'decodes', noop)(preds)
            x,y,its,outs = self.valid_dl.show_results(b, out, show=False, max_n=self.n_preds)
            pred_log = sum([wand_process(x, y, s, o) for s,o in zip(its, outs)], [])
            wandb.log({"Prediction Samples": pred_log}, commit=False)
        wandb.log({n:s for n,s in zip(self.recorder.metric_names, self.recorder.log) if n!='train_loss'})

#Cell
@typedispatch
def wand_process(x:TensorImage, y, sample, out):
    "Process `sample` and `out` depending on the type of `x/y`"
    img = sample[0].permute(1,2,0)
    res = [wandb.Image(img, caption='Input data', grouping=3)]
    for t, capt in ((out[0], "Prediction"), (sample[1], "Ground Truth")):
        # Resize plot to image resolution (from https://stackoverflow.com/a/13714915)
        my_dpi = 100
        fig = plt.figure(frameon=False, dpi=my_dpi)
        h, w = img.shape[:2]
        fig.set_size_inches(w / my_dpi, h / my_dpi)
        ax = plt.Axes(fig, [0., 0., 1., 1.])
        ax.set_axis_off()
        fig.add_axes(ax)
        # Superimpose label or prediction to input image
        ax = img.show(ctx=ax)
        ax = t.show(ctx=ax)
        res.append(wandb.Image(fig, caption=capt))
        plt.close(fig)
    return res

#Cell
@typedispatch
def wand_process(x:TensorImage, y:(TensorCategory,TensorMultiCategory), sample, out):
    img = sample[0].permute(1,2,0)
    return [wandb.Image(img, caption=f'Ground Truth: {sample[1]}\nPrediction: {out[0]}')]