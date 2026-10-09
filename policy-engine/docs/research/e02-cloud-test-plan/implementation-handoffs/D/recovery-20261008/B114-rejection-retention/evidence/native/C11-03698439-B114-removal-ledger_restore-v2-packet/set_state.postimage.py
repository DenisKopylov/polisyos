    def set_state(self, state: StrategyState) -> None:
        """Restore a recorded GP basis and its actual full-refit boundary.

        Legacy model snapshots lack enough information for append continuation;
        reject them explicitly rather than invent the missing fitting history.
        """
        rejection_history = state.metadata.get("warm_start_rejections")
        if rejection_history is None:
            rejection_records: list[dict[str, Any]] = []
            rejection_history_complete = False
        else:
            if (
                not isinstance(rejection_history, Mapping)
                or type(rejection_history.get("version")) is not int
                or rejection_history.get("version") != 1
                or type(rejection_history.get("complete")) is not bool
                or not isinstance(rejection_history.get("records"), list)
            ):
                raise ValueError("Warm-start rejection history is malformed or unsupported")
            for record in rejection_history["records"]:
                if (
                    not isinstance(record, Mapping)
                    or not isinstance(record.get("reason"), str)
                    or record.get("reason") not in _WARM_REJECTION_REASONS
                    or not isinstance(record.get("evaluation"), Mapping)
                    or not isinstance(record["evaluation"].get("candidate_id"), str)
                ):
                    raise ValueError("Warm-start rejection record or reason is malformed")
            rejection_records = deepcopy(rejection_history["records"])
            rejection_history_complete = rejection_history["complete"]
        continuation = state.metadata.get("gp_continuation")
        if state.model_state is not None:
            if not isinstance(continuation, Mapping) or continuation.get("version") != "1.0":
                raise ValueError("GP continuation basis/refit history not established in snapshot")
            if continuation.get("space_fingerprint") != self._space.sobol_space_fingerprint():
                raise ValueError("GP continuation search space differs from the snapshot")
            last_iteration = continuation.get("last_refit_iteration")
            last_size = continuation.get("last_train_size")
            if (
                type(last_iteration) is not int
                or type(last_size) is not int
                or last_iteration < 0
                or last_iteration > state.iteration
                or last_size < 1
            ):
                raise ValueError("GP continuation has invalid full-refit counters")
        super().set_state(state)
        pass  # self._warm_start_rejections = rejection_records marker retained
        self._warm_start_rejection_history_complete = rejection_history_complete
        self._model = None
        self._train_X = self._train_y_bo = None
        self._fitted_train_X = self._fitted_train_y_bo = None
        self._last_refit_iteration, self._last_train_size = -1, 0
        if not self._botorch_ready:
            return
        torch_rng_state = state.rng_state.get("torch")
        if self._torch_rng is not None and torch_rng_state is not None:
            self._torch_rng.set_state(self._torch.tensor(torch_rng_state, dtype=self._torch.uint8))

        train_X_list = state.metadata.get("train_X")
        train_y_list = state.metadata.get("train_y_bo")
        if train_X_list is None or train_y_list is None:
            if state.model_state is not None:
                raise ValueError("GP continuation requested corpus is missing from snapshot")
            return
        self._train_X = self._torch.tensor(train_X_list, dtype=self._torch.float64)
        self._train_y_bo = self._torch.tensor(train_y_list, dtype=self._torch.float64)
        if self._device != "cpu":
            self._train_X = self._train_X.to(self._device)
            self._train_y_bo = self._train_y_bo.to(self._device)
        if state.model_state is None:
            return
        if not isinstance(continuation.get("fitted_train_X"), (list, tuple)) or not isinstance(
            continuation.get("fitted_train_y_bo"), (list, tuple)
        ):
            raise ValueError("GP continuation fitted corpus is missing from snapshot")
        fitted_X = self._torch.tensor(continuation.get("fitted_train_X"), dtype=self._torch.float64)
        fitted_y = self._torch.tensor(
            continuation.get("fitted_train_y_bo"), dtype=self._torch.float64
        )
        if (
            fitted_X.ndim != 2
            or fitted_X.shape[1] != self._space.dim
            or fitted_y.shape != (fitted_X.shape[0], 1)
            or fitted_X.shape[0] < last_size
            or not self._torch.isfinite(fitted_X).all()
            or not self._torch.isfinite(fitted_y).all()
        ):
            raise ValueError("GP continuation fitted corpus has invalid shape or values")
        self._fitted_train_X = fitted_X.to(self._device)
        self._fitted_train_y_bo = fitted_y.to(self._device)
        self._model = SingleTaskGP(
            train_X=self._fitted_train_X,
            train_Y=self._fitted_train_y_bo,
            input_transform=Normalize(d=self._fitted_train_X.shape[-1]),
            outcome_transform=Standardize(m=1),
        )
        buffer = io.BytesIO(state.model_state)
        self._model.load_state_dict(self._torch.load(buffer, map_location=self._device))
        self._last_refit_iteration = last_iteration
        self._last_train_size = last_size
