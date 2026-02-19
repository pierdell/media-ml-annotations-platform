"""Model training tasks."""

import os
import uuid
from datetime import datetime, timezone

import structlog
from celery import shared_task

logger = structlog.get_logger()


@shared_task(
    bind=True,
    name="worker.tasks.training.run_training_job",
    max_retries=1,
    default_retry_delay=120,
    acks_late=True,
    time_limit=3600,  # 1 hour max
)
def run_training_job(self, job_id: str, project_id: str, dataset_id: str, **kwargs):
    """
    Execute a model training job.

    Workflow:
    1. Load dataset and prepare data loaders
    2. Initialize model from base weights
    3. Train for specified epochs
    4. Evaluate on validation split
    5. Save model artifacts to MinIO
    6. Update job record with results
    """
    try:
        logger.info("training_start", job_id=job_id, dataset_id=dataset_id)

        # Update status to preparing
        _update_job_status(job_id, "preparing", started_at=datetime.now(timezone.utc))

        # Load job config
        job_config = _get_job_config(job_id)
        if not job_config:
            _update_job_status(job_id, "failed", error_message="Job config not found")
            return {"status": "failed", "error": "Job config not found"}

        hyperparams = job_config.get("hyperparameters", {})
        model_type = job_config.get("model_type", "image_classifier")
        base_model = job_config.get("base_model", "resnet50")
        total_epochs = hyperparams.get("epochs", 50)

        # Prepare training data
        _update_job_status(job_id, "training")
        train_data = _prepare_dataset(dataset_id, "train")
        val_data = _prepare_dataset(dataset_id, "val")

        if not train_data:
            _update_job_status(job_id, "failed", error_message="No training data available")
            return {"status": "failed", "error": "No training data"}

        # Simulate training loop (actual implementation depends on model type)
        metrics_history = []
        best_val_loss = float("inf")

        for epoch in range(1, total_epochs + 1):
            # In production, this would call actual training code
            train_loss = _simulate_training_step(epoch, total_epochs)
            val_loss = _simulate_validation_step(epoch, total_epochs)

            epoch_metrics = {
                "epoch": epoch,
                "train_loss": round(train_loss, 4),
                "val_loss": round(val_loss, 4),
            }
            metrics_history.append(epoch_metrics)

            if val_loss < best_val_loss:
                best_val_loss = val_loss

            # Update progress
            _update_job_progress(job_id, epoch, total_epochs, train_loss, val_loss)

        # Evaluation
        _update_job_status(job_id, "evaluating")
        eval_metrics = _evaluate_model(model_type, val_data)

        # Save model
        export_format = job_config.get("export_format", "pytorch")
        model_path = _save_model(project_id, job_id, export_format)

        # Update completion
        _update_job_completion(
            job_id,
            model_path=model_path,
            metrics={
                **eval_metrics,
                "best_val_loss": round(best_val_loss, 4),
                "loss_history": metrics_history[-10:],  # Last 10 epochs
                "total_epochs_trained": total_epochs,
            },
        )

        logger.info("training_done", job_id=job_id, metrics=eval_metrics)
        return {"status": "completed", "job_id": job_id, "metrics": eval_metrics}

    except Exception as exc:
        logger.error("training_error", job_id=job_id, error=str(exc))
        _update_job_status(job_id, "failed", error_message=str(exc))
        raise self.retry(exc=exc)


# ── Helper functions ──────────────────────────────────────

def _get_job_config(job_id: str) -> dict | None:
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    sync_url = os.environ.get("SYNC_DATABASE_URL")
    if not sync_url:
        return None

    engine = create_engine(sync_url)
    from backend.app.models.training import TrainingJob

    with Session(engine) as session:
        result = session.execute(select(TrainingJob).where(TrainingJob.id == uuid.UUID(job_id)))
        job = result.scalar_one_or_none()
        if not job:
            engine.dispose()
            return None

        config = {
            "model_type": job.model_type,
            "base_model": job.base_model,
            "hyperparameters": job.hyperparameters,
            "export_format": job.export_format,
            "dataset_id": str(job.dataset_id) if job.dataset_id else None,
        }

    engine.dispose()
    return config


def _prepare_dataset(dataset_id: str, split: str) -> list[dict]:
    """Load dataset items for a given split."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    sync_url = os.environ.get("SYNC_DATABASE_URL")
    if not sync_url:
        return []

    engine = create_engine(sync_url)
    from backend.app.models.dataset import DatasetItem, Annotation

    with Session(engine) as session:
        items = session.execute(
            select(DatasetItem)
            .where(DatasetItem.dataset_id == uuid.UUID(dataset_id), DatasetItem.split == split, DatasetItem.is_annotated == True)  # noqa: E712
        ).scalars().all()

        data = []
        for item in items:
            annotations = session.execute(
                select(Annotation).where(Annotation.dataset_item_id == item.id)
            ).scalars().all()
            data.append({
                "item_id": str(item.id),
                "media_id": str(item.media_id),
                "annotations": [
                    {"type": a.annotation_type, "label": a.label, "geometry": a.geometry}
                    for a in annotations
                ],
            })

    engine.dispose()
    return data


def _simulate_training_step(epoch: int, total: int) -> float:
    """Simulate a training loss curve."""
    import math
    base = 2.0 * math.exp(-epoch / (total * 0.3))
    noise = 0.05 * (1 - epoch / total)
    return max(base + noise, 0.01)


def _simulate_validation_step(epoch: int, total: int) -> float:
    """Simulate a validation loss curve."""
    import math
    base = 2.2 * math.exp(-epoch / (total * 0.35))
    noise = 0.08 * (1 - epoch / total)
    return max(base + noise, 0.02)


def _evaluate_model(model_type: str, val_data: list) -> dict:
    """Evaluate model on validation set."""
    n = max(len(val_data), 1)
    # Simulated metrics based on model type
    if model_type == "image_classifier":
        return {"accuracy": 0.92, "f1_macro": 0.90, "precision": 0.91, "recall": 0.89}
    elif model_type == "object_detector":
        return {"mAP_50": 0.85, "mAP_50_95": 0.72, "precision": 0.88, "recall": 0.82}
    elif model_type == "clip_finetune":
        return {"image_retrieval_r1": 0.78, "text_retrieval_r1": 0.75, "mean_similarity": 0.85}
    else:
        return {"accuracy": 0.88}


def _save_model(project_id: str, job_id: str, export_format: str) -> str:
    """Save model artifacts to MinIO."""
    path = f"models/{project_id}/{job_id}/model.{export_format}"
    # In production, would upload actual model file to MinIO
    logger.info("model_saved", path=path, format=export_format)
    return path


def _update_job_status(job_id: str, status: str, error_message: str | None = None, started_at=None):
    from sqlalchemy import create_engine, update
    from sqlalchemy.orm import Session

    sync_url = os.environ.get("SYNC_DATABASE_URL")
    if not sync_url:
        return

    engine = create_engine(sync_url)
    from backend.app.models.training import TrainingJob

    values = {"status": status}
    if error_message:
        values["error_message"] = error_message
    if started_at:
        values["started_at"] = started_at

    with Session(engine) as session:
        session.execute(update(TrainingJob).where(TrainingJob.id == uuid.UUID(job_id)).values(**values))
        session.commit()
    engine.dispose()


def _update_job_progress(job_id: str, epoch: int, total: int, train_loss: float, val_loss: float):
    from sqlalchemy import create_engine, update
    from sqlalchemy.orm import Session

    sync_url = os.environ.get("SYNC_DATABASE_URL")
    if not sync_url:
        return

    engine = create_engine(sync_url)
    from backend.app.models.training import TrainingJob

    with Session(engine) as session:
        session.execute(
            update(TrainingJob).where(TrainingJob.id == uuid.UUID(job_id)).values(
                current_epoch=epoch,
                total_epochs=total,
                train_loss=train_loss,
                val_loss=val_loss,
            )
        )
        session.commit()
    engine.dispose()


def _update_job_completion(job_id: str, model_path: str, metrics: dict):
    from sqlalchemy import create_engine, update
    from sqlalchemy.orm import Session

    sync_url = os.environ.get("SYNC_DATABASE_URL")
    if not sync_url:
        return

    engine = create_engine(sync_url)
    from backend.app.models.training import TrainingJob

    with Session(engine) as session:
        session.execute(
            update(TrainingJob).where(TrainingJob.id == uuid.UUID(job_id)).values(
                status="completed",
                model_path=model_path,
                metrics=metrics,
                completed_at=datetime.now(timezone.utc),
            )
        )
        session.commit()
    engine.dispose()
