import argparse
import cv2
import math
import numpy as np
import os
from datetime import datetime, timedelta
from enum import Enum, auto
from tqdm import tqdm

GREEN = (0, 128, 0)
RED = (0, 0, 255)
WHITE = (255, 255, 255)


def parse_arg():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file_name", type=str)
    parser.add_argument("--task_period_list", "-p", nargs="*", default=[])
    parser.add_argument("--task_success_list", "-s", nargs="*", default=[])
    parser.add_argument(
        "--output_file_name",
        "-o",
        type=str,
        default="./output_" + os.path.splitext(os.path.basename(__file__))[0] + ".mp4",
    )
    parser.add_argument("--column_num", "-n", type=int, default=3)
    parser.add_argument("--codec", "-c", type=str, default="MP4V")
    parser.add_argument("--border_size", "-b", type=int, default=15)
    parser.add_argument(
        "--shift_seconds",
        "-t",
        type=float,
        default=0.5,
        help="remove seconds when starting from a dull screen",
    )
    parser.add_argument(
        "--satur_thresh",
        "-e",
        type=float,
        default=10.0,
        help="threshold used to determine if the screen is saturated",
    )
    parser.add_argument(
        "--satur_detection_region_ratio",
        "-r",
        nargs=4,
        metavar=("LEFTTOP_X", "LEFTTOP_Y", "SIZE_X", "SIZE_Y"),
        type=float,
        default=[0, 0, 1, 1],
        help="ratio for the region used to detect if the screen is saturated",
    )
    parser.add_argument("--quiet", "-q", action="store_true")
    args = parser.parse_args()

    for i in range(len(args.satur_detection_region_ratio)):
        condition_str = f"0.0 <= args.satur_detection_region_ratio[{i}] <= 1.0"
        assert eval(condition_str), (
            "\n\t"
            "asserted: " + condition_str + "\n\t"
            f"{args.satur_detection_region_ratio[i]=}"
        )

    for i in range(len(args.satur_detection_region_ratio)):
        condition_str = "args.input_file_name != args.output_file_name"
        assert eval(condition_str), (
            "\n\t"
            "asserted: " + condition_str + "\n\t"
            f"{(args.input_file_name, args.output_file_name)=}"
        )

    if not args.quiet:
        print(f"{args=}")
    return args


def get_video_properties(input_file_name):
    video = cv2.VideoCapture(input_file_name)
    frame_rate = video.get(cv2.CAP_PROP_FPS)
    frame_w = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    video.release()
    return frame_rate, frame_w, frame_h, frame_count


def time_str_to_seconds(time_str):
    time_obj = datetime.strptime(time_str, "%M:%S.%f")
    return timedelta(
        minutes=time_obj.minute,
        seconds=time_obj.second,
        microseconds=time_obj.microsecond,
    ).total_seconds()


def seconds_to_time_str(seconds):
    formatted_time = datetime(
        year=1, month=1, day=1, hour=0, minute=0, second=0
    ) + timedelta(seconds=seconds)
    time_str = formatted_time.strftime("%M:%S.%f")
    tparts = time_str.split(".")
    return f"{tparts[0]}.{tparts[1][:2]}"


class TaskEventHandler:
    class Stat(Enum):
        INITIAL = auto()
        STARTED = auto()
        STOPPED = auto()

    PRINT_INTERVAL_VIDEO_SEC = 5

    def __init__(
        self, task_period_list, frame_rate, shift_seconds, satur_thresh, quiet
    ):
        self.state = self.Stat.INITIAL

        self.env_idx = 0
        self.task_period_list = task_period_list
        self.frame_rate = frame_rate
        self.shift_seconds = shift_seconds
        self.satur_thresh = satur_thresh
        self.quiet = quiet

    def start_env(self, i_frame_curr, region_satur_mean):
        self.state = self.Stat.STARTED

        seconds_curr = i_frame_curr / self.frame_rate
        time_str = seconds_to_time_str(seconds_curr)
        env_str = f"env={self.env_idx:<2}"
        tqdm.write(
            "\t".join(
                [
                    "",
                    f"{region_satur_mean=:>7.3f}",
                    f"{self.satur_thresh=:>7.3f}",
                    time_str,
                    self.start_env.__name__,
                    env_str,
                ]
            )
        )
        self.task_period_list.append(f"{time_str}-")

    def stop_env(self, i_frame_curr, region_satur_mean):
        self.state = self.Stat.STOPPED

        seconds_curr = i_frame_curr / self.frame_rate
        time_str = seconds_to_time_str(seconds_curr)
        env_str = f"env={self.env_idx:<2}"
        tqdm.write(
            "\t".join(
                [
                    "",
                    f"{region_satur_mean=:>7.3f}",
                    f"{self.satur_thresh=:>7.3f}",
                    time_str,
                    self.stop_env.__name__,
                    env_str,
                ]
            )
        )
        self.task_period_list[-1] += time_str
        self.env_idx += 1

    def initial_stop(self):
        self.state = self.Stat.STOPPED

    def handle(self, is_satur_screen, i_frame_curr, region_satur_mean):
        if (not self.quiet) and (
            i_frame_curr % (self.frame_rate * self.PRINT_INTERVAL_VIDEO_SEC) == 0
        ):
            seconds_curr = i_frame_curr / self.frame_rate
            time_str = seconds_to_time_str(seconds_curr)
            env_str = (
                f"env={self.env_idx:<2}"
                if self.state == self.Stat.STARTED
                else " " * len("env= 0")
            )
            tqdm.write(
                "\t".join(
                    [
                        "",
                        f"{region_satur_mean=:>7.3f}",
                        f"{self.satur_thresh=:>7.3f}",
                        time_str,
                        " " * len(self.start_env.__name__),
                        env_str,
                        f"{self.state.name}",
                    ]
                )
            )
        if self.state == self.Stat.STARTED:
            if not is_satur_screen:
                self.stop_env(
                    i_frame_curr - self.shift_seconds * self.frame_rate,
                    region_satur_mean,
                )
        elif self.state == self.Stat.STOPPED:
            if not not is_satur_screen:
                self.start_env(
                    i_frame_curr + self.shift_seconds * self.frame_rate,
                    region_satur_mean,
                )
        elif self.state == self.Stat.INITIAL:
            if not is_satur_screen:
                self.initial_stop()
            else:
                self.start_env(i_frame_curr, region_satur_mean)
        else:
            raise AssertionError(f"{self.state=}")


def is_saturated(frame, satur_thresh, lefttop_x, lefttop_y, size_x, size_y):
    crop_x = round(frame.shape[1] * lefttop_x)
    crop_y = round(frame.shape[0] * lefttop_y)
    crop_w = round(frame.shape[1] * size_x)
    crop_h = round(frame.shape[0] * size_y)
    region = frame[crop_y : crop_y + crop_h, crop_x : crop_x + crop_w]
    region_hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    region_satur = region_hsv[..., 1]
    region_satur_mean = region_satur.mean()
    is_saturated = region_satur_mean >= satur_thresh
    return is_saturated, region_satur_mean


def update_task_period_list_ifneeded(
    task_period_list,
    input_file_name,
    shift_seconds,
    satur_thresh,
    satur_detection_region_ratio,
    quiet,
):
    if len(task_period_list) >= 1:
        return task_period_list

    frame_rate, frame_w, frame_h, frame_count = get_video_properties(input_file_name)
    video = cv2.VideoCapture(input_file_name)
    task_event_handler = TaskEventHandler(
        task_period_list, frame_rate, shift_seconds, satur_thresh, quiet
    )

    for i_frame_curr in tqdm(
        range(frame_count), desc=update_task_period_list_ifneeded.__name__
    ):
        ret, frame = video.read()
        if not ret:
            continue
        is_satur_screen, region_satur_mean = is_saturated(
            frame, satur_thresh, *satur_detection_region_ratio
        )

        task_event_handler.handle(is_satur_screen, i_frame_curr, region_satur_mean)
    task_event_handler.handle(
        is_satur_screen=False, i_frame_curr=frame_count, region_satur_mean=-float("inf")
    )

    video.release()
    return task_event_handler.task_period_list


def parse_frame_periods(
    task_period_list,
    input_file_name,
    shift_seconds,
    satur_thresh,
    satur_detection_region_ratio,
):
    return_frame_periods = list()

    frame_rate, _, _, _ = get_video_properties(input_file_name)
    parsed_values = [
        [
            time_str_to_seconds(time_str) * frame_rate
            for time_str in start_end_time_str.split("-")
        ]
        for start_end_time_str in task_period_list
    ]

    video = cv2.VideoCapture(input_file_name)

    for i_frame_start, i_frame_end in parsed_values:
        video.set(cv2.CAP_PROP_POS_FRAMES, i_frame_start)
        ret, frame_start = video.read()
        assert ret
        is_satur_screen, region_satur_mean = is_saturated(
            frame_start, satur_thresh, *satur_detection_region_ratio
        )
        shift_frame = (shift_seconds * frame_rate) if not is_satur_screen else 0.0
        return_frame_periods.append([i_frame_start + shift_frame, i_frame_end])

    video.release()
    return return_frame_periods


def init_final_frames(
    max_trim_len,
    task_success_list,
    frame_h,
    frame_w,
    border_size,
    row_num,
    column_num,
    quiet,
):
    if not quiet:
        print(f"{init_final_frames.__name__}, create new array ...")
    if len(task_success_list) == 0:
        final_frames = np.full(
            (
                max_trim_len,  # frame
                (frame_h + 2 * border_size) * row_num,  # height
                (frame_w + 2 * border_size) * column_num,  # width
                3,  # channel
            ),
            WHITE,
            dtype=np.uint8,
        )
        return final_frames
    final_frames = np.empty(
        (
            max_trim_len,  # frame
            (frame_h + 2 * border_size) * row_num,  # height
            (frame_w + 2 * border_size) * column_num,  # width
            3,  # channel
        ),
        dtype=np.uint8,
    )

    if not quiet:
        print(f"{init_final_frames.__name__}, set elements ...")
    for i_subvideo, is_task_successful in enumerate(
        tqdm(list([int(x) for x in task_success_list]))
    ):
        assert is_task_successful in (0, 1)

        # outside frame
        x_draw = (frame_w + 2 * border_size) * (i_subvideo % column_num)
        y_draw = (frame_h + 2 * border_size) * (i_subvideo // column_num)
        final_frames[
            :,  # frame
            y_draw : y_draw + (frame_h + 2 * border_size),  # height
            x_draw : x_draw + (frame_w + 2 * border_size),  # width
            :,  # channel
        ] = GREEN if is_task_successful else RED

        # inside
        x_draw = border_size + (frame_w + 2 * border_size) * (i_subvideo % column_num)
        y_draw = border_size + (frame_h + 2 * border_size) * (i_subvideo // column_num)
        final_frames[
            :,  # frame
            y_draw : y_draw + frame_h,  # height
            x_draw : x_draw + frame_w,  # width
            :,  # channel
        ] = WHITE

    return final_frames


def read_video(input_file_name, final_frames, frame_periods, column_num, border_size):
    _, frame_w, frame_h, frame_count = get_video_properties(input_file_name)
    video = cv2.VideoCapture(input_file_name)

    for i_frame_curr in tqdm(range(frame_count), desc=read_video.__name__):
        ret, frame = video.read()
        if not ret:
            continue
        for i_subvideo, (i_frame_start, i_frame_end) in enumerate(frame_periods):
            i_frame_draw = int(
                np.clip(i_frame_curr - i_frame_start, 0, final_frames.shape[0] - 1)
            )
            x_draw = border_size + (frame_w + 2 * border_size) * (
                i_subvideo % column_num
            )
            y_draw = border_size + (frame_h + 2 * border_size) * (
                i_subvideo // column_num
            )
            if i_frame_curr < i_frame_start:
                continue
            if i_frame_curr <= i_frame_end:
                final_frames[
                    i_frame_draw,  # frame
                    y_draw : y_draw + frame_h,  # height
                    x_draw : x_draw + frame_w,  # width
                    ...,  # channel
                ] = frame
                if (i_frame_end - i_frame_curr) <= 1.0:
                    final_frames[
                        i_frame_draw:,  # frame
                        y_draw : y_draw + frame_h,  # height
                        x_draw : x_draw + frame_w,  # width
                        ...,  # channel
                    ] = frame

    video.release()
    return final_frames


def write_video(final_frames, output_file_name, frame_rate, codec):
    output_dir_name = os.path.dirname(output_file_name)
    if not os.path.exists(output_dir_name):
        os.makedirs(output_dir_name)

    fourcc = cv2.VideoWriter_fourcc(*codec)
    writer_out = cv2.VideoWriter(
        output_file_name,
        fourcc,
        frame_rate,
        (final_frames.shape[2], final_frames.shape[1]),
    )

    for i_frame_curr in tqdm(
        range(final_frames.shape[0]), desc=writer_out.write.__name__
    ):
        writer_out.write(final_frames[i_frame_curr, ...])

    writer_out.release()


def main():
    args = parse_arg()

    task_period_list = args.task_period_list
    if len(task_period_list) == 0:
        if not args.quiet:
            print(f"{update_task_period_list_ifneeded.__name__} ...")
        task_period_list = update_task_period_list_ifneeded(
            task_period_list,
            args.input_file_name,
            args.shift_seconds,
            args.satur_thresh,
            args.satur_detection_region_ratio,
            args.quiet,
        )
        if not args.quiet:
            print(f"{task_period_list=}")
    assert len(task_period_list) >= 1, f"{len(task_period_list)=}"
    if len(args.task_success_list) >= 1:
        if len(args.task_success_list) != len(task_period_list):
            raise ValueError(
                (
                    "lengths of task_success_list "
                    f"({len(args.task_success_list)}) and "
                    "task_period_list "
                    f"({len(task_period_list)}) must be same."
                )
            )

    row_num = math.ceil(len(args.task_period_list) / args.column_num)

    if not args.quiet:
        print(f"{parse_frame_periods.__name__} ...")
    frame_periods = parse_frame_periods(
        task_period_list,
        args.input_file_name,
        args.shift_seconds,
        args.satur_thresh,
        args.satur_detection_region_ratio,
    )
    max_trim_len = int(math.ceil(max([e - s for s, e in frame_periods])))

    if not args.quiet:
        print(f"{get_video_properties.__name__} ...")
    frame_rate, frame_w, frame_h, _ = get_video_properties(args.input_file_name)

    if not args.quiet:
        print(f"{init_final_frames.__name__} ...")
    final_frames = init_final_frames(
        max_trim_len,
        args.task_success_list,
        frame_h,
        frame_w,
        args.border_size,
        row_num,
        args.column_num,
        args.quiet,
    )

    if not args.quiet:
        print(f"{read_video.__name__} ...")
    final_frames = read_video(
        args.input_file_name,
        final_frames,
        frame_periods,
        args.column_num,
        args.border_size,
    )

    if not args.quiet:
        print(f"{write_video.__name__} ...")
    write_video(final_frames, args.output_file_name, frame_rate, args.codec)

    print(f"[tile_rollout_videos] Save a video: {args.output_file_name}")
    if not args.quiet:
        print("Done.")


if __name__ == "__main__":
    main()
